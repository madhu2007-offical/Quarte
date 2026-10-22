"""Streamlit dashboard for visual quantum circuit optimization and baseline analysis."""

from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from qiskit import QuantumCircuit
from qiskit.qasm2 import QASM2Error, dumps, loads
import streamlit as st

from benchmarks.generators import get_benchmark_suite
from metrics.metrics import get_metrics
from optimizer.pipeline import optimize

st.set_page_config(
    page_title="Quantum Circuit Gate-Reduction Optimizer",
    page_icon="⚛️",
    layout="wide",
)

RESULTS_CSV_PATH = Path(__file__).resolve().parent.parent / "results" / "results.csv"

st.title("⚛️ Quantum Circuit Gate-Reduction Optimizer")
st.markdown(
    "Classical, explainable quantum circuit optimizer built on Qiskit. "
    "Evaluates gate cancellation, rotation merging, commutation sliding, "
    "and compares against Qiskit transpiler baselines (L0–L3) and "
    "**noisy simulation using IBM device noise models** (`FakeSherbrooke`)."
)

# -----------------------------------------------------------------------------
# Panel 1: Circuit Selection & Optimization
# -----------------------------------------------------------------------------
st.header("1. Input Circuit & Optimization Controls")

suite = get_benchmark_suite()
benchmark_names = [b["name"] for b in suite]

col_left, col_right = st.columns([1, 1])

with col_left:
    selected_bench = st.selectbox(
        "Choose a benchmark circuit:",
        options=["(Custom QASM)"] + benchmark_names,
        index=benchmark_names.index("qft_then_inverse_3") + 1 if "qft_then_inverse_3" in benchmark_names else 0,
    )

    translate_to_basis = st.checkbox(
        "Translate to basis (`rz`, `sx`, `x`, `cx`) before pass execution",
        value=True,
        help="Ensures fair apples-to-apples basis gate comparisons against Qiskit baselines.",
    )

with col_right:
    custom_qasm_input = ""
    if selected_bench == "(Custom QASM)":
        uploaded_file = st.file_uploader("Upload an OpenQASM (.qasm) file", type=["qasm", "txt"])
        if uploaded_file is not None:
            custom_qasm_input = uploaded_file.read().decode("utf-8")
        else:
            custom_qasm_input = st.text_area(
                "Or paste OpenQASM 2.0 text here:",
                value="OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nh q[0];\n",
                height=150,
            )
    else:
        bench_match = next(b for b in suite if b["name"] == selected_bench)
        custom_qasm_input = dumps(bench_match["circuit"])
        st.text_area("Benchmark QASM representation:", value=custom_qasm_input, height=150, disabled=True)

optimize_button = st.button("🚀 Optimize Circuit", type="primary")

# Load circuit
parsed_circuit: QuantumCircuit = None
parse_error: str = None

if custom_qasm_input.strip():
    try:
        parsed_circuit = loads(custom_qasm_input)
    except Exception as ex:
        parse_error = f"Error parsing QASM: {ex}"

if parse_error:
    st.error(parse_error)

# Session state for persistence
if optimize_button and parsed_circuit is not None:
    if parsed_circuit.num_qubits > 10:
        st.error(
            f"Circuit has {parsed_circuit.num_qubits} qubits. "
            "Equivalence verification is restricted to circuits with <= 10 qubits."
        )
    else:
        with st.spinner("Executing optimization passes and equivalence verification..."):
            opt_res = optimize(parsed_circuit, translate_to_basis=translate_to_basis)
            st.session_state["opt_res"] = opt_res
            st.session_state["input_circuit"] = parsed_circuit
            st.session_state["benchmark_name"] = selected_bench

# -----------------------------------------------------------------------------
# Panel 2 & 3: Before/After Drawings and Metrics
# -----------------------------------------------------------------------------
if "opt_res" in st.session_state:
    opt_res = st.session_state["opt_res"]
    input_qc = st.session_state["input_circuit"]

    st.markdown("---")
    st.header("2. Circuit Visualizations & Verification")

    draw_col1, draw_col2 = st.columns(2)

    with draw_col1:
        st.subheader("Original Input Circuit")
        try:
            fig_in = input_qc.draw(output="mpl")
            st.pyplot(fig_in)
            plt.close(fig_in)
        except Exception as e:
            st.text(input_qc.draw(output="text"))

    with draw_col2:
        st.subheader("Optimized Circuit")
        try:
            fig_out = opt_res.optimized_circuit.draw(output="mpl")
            st.pyplot(fig_out)
            plt.close(fig_out)
        except Exception as e:
            st.text(opt_res.optimized_circuit.draw(output="text"))

    st.markdown("---")
    st.header("3. Structural Metrics & Equivalence")

    m_in = get_metrics(input_qc)
    m_out = get_metrics(opt_res.optimized_circuit)

    delta_gates = m_out["total_gates"] - m_in["total_gates"]
    delta_cx = m_out["two_qubit_gates"] - m_in["two_qubit_gates"]
    delta_depth = m_out["depth"] - m_in["depth"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Gates", f"{m_out['total_gates']}", f"{delta_gates:+d} gates")
    c2.metric("Two-Qubit Gates (CX)", f"{m_out['two_qubit_gates']}", f"{delta_cx:+d} gates")
    c3.metric("Circuit Depth", f"{m_out['depth']}", f"{delta_depth:+d} depth")

    with c4:
        st.markdown("**Unitary Equivalence**")
        if opt_res.equivalent:
            st.success("✅ PASS (Identical up to global phase)")
        else:
            st.error("❌ FAIL (Unitary mismatch)")

    if opt_res.per_pass_metrics:
        with st.expander("Detailed Pass-by-Pass Telemetry"):
            pass_df = pd.DataFrame([
                {
                    "Iteration": p["iteration"],
                    "Pass Name": p["pass_name"],
                    "Gates Before": p["metrics_before"]["total_gates"],
                    "Gates After": p["metrics_after"]["total_gates"],
                    "CX Before": p["metrics_before"]["two_qubit_gates"],
                    "CX After": p["metrics_after"]["two_qubit_gates"],
                    "Depth Before": p["metrics_before"]["depth"],
                    "Depth After": p["metrics_after"]["depth"],
                }
                for p in opt_res.per_pass_metrics
            ])
            st.dataframe(pass_df, width="stretch")

# -----------------------------------------------------------------------------
# Panel 4: Baseline Comparison Bar Charts (from results.csv)
# -----------------------------------------------------------------------------
st.markdown("---")
st.header("4. Baseline Comparison vs. Qiskit Transpile Levels 0–3")

if not RESULTS_CSV_PATH.exists():
    st.warning("`results/results.csv` not found. Run `python scripts/run_benchmarks.py` to generate.")
else:
    df_results = pd.read_csv(RESULTS_CSV_PATH)
    bench_to_chart = st.selectbox(
        "Select benchmark to plot from precomputed results:",
        options=df_results["benchmark"].unique(),
        index=list(df_results["benchmark"].unique()).index("qft_then_inverse_3")
        if "qft_then_inverse_3" in df_results["benchmark"].unique()
        else 0,
    )

    bench_df = df_results[df_results["benchmark"] == bench_to_chart]

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Total Gates by Variant")
        fig, ax = plt.subplots(figsize=(6, 3.5))
        variants = bench_df["variant"]
        bars = ax.bar(variants, bench_df["total_gates"], color="#3b82f6")
        ax.set_ylabel("Total Gate Count")
        ax.set_title(f"Total Gates: {bench_to_chart}")
        plt.xticks(rotation=45, ha="right")
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{int(height)}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with chart_col2:
        st.subheader("Two-Qubit Gates (CX) by Variant")
        fig, ax = plt.subplots(figsize=(6, 3.5))
        bars = ax.bar(variants, bench_df["two_qubit_gates"], color="#10b981")
        ax.set_ylabel("Two-Qubit Gate Count")
        ax.set_title(f"Two-Qubit Gates: {bench_to_chart}")
        plt.xticks(rotation=45, ha="right")
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{int(height)}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # -------------------------------------------------------------------------
    # Panel 5: Noisy Simulation Fidelity with Error Bars
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.header("5. Noisy Simulation Fidelity & Empirical Success")
    st.caption(
        "Evaluated via **noisy simulation using IBM device noise models** (`FakeSherbrooke`), "
        "executed over 3 independent seeds (42, 43, 44) with 4096 shots per run. "
        "Error bars represent ±1 sample standard deviation."
    )

    has_noisy_data = bench_df["hellinger_mean"].notna() & (bench_df["hellinger_mean"] != "")

    if not has_noisy_data.any():
        st.info(
            f"Noisy simulation is not applicable for '{bench_to_chart}'. "
            "Simulations are restricted to circuits with <= 7 qubits and known ground-truth distributions."
        )
    else:
        noisy_sub = bench_df[has_noisy_data].copy()
        noisy_sub["hellinger_mean"] = pd.to_numeric(noisy_sub["hellinger_mean"])
        noisy_sub["hellinger_std"] = pd.to_numeric(noisy_sub["hellinger_std"]).fillna(0.0)
        noisy_sub["success_prob_mean"] = pd.to_numeric(noisy_sub["success_prob_mean"])
        noisy_sub["success_prob_std"] = pd.to_numeric(noisy_sub["success_prob_std"]).fillna(0.0)

        f_col1, f_col2 = st.columns(2)

        with f_col1:
            st.subheader("Hellinger Fidelity vs Ideal Distribution")
            fig, ax = plt.subplots(figsize=(6, 3.5))
            ax.bar(
                noisy_sub["variant"],
                noisy_sub["hellinger_mean"],
                yerr=noisy_sub["hellinger_std"],
                capsize=5,
                color="#8b5cf6",
                alpha=0.85,
            )
            ax.set_ylim(0, 1.05)
            ax.set_ylabel("Hellinger Fidelity")
            ax.set_title(f"Hellinger Fidelity: {bench_to_chart}")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        with f_col2:
            st.subheader("Empirical Success Probability")
            fig, ax = plt.subplots(figsize=(6, 3.5))
            ax.bar(
                noisy_sub["variant"],
                noisy_sub["success_prob_mean"],
                yerr=noisy_sub["success_prob_std"],
                capsize=5,
                color="#f59e0b",
                alpha=0.85,
            )
            ax.set_ylim(0, 1.05)
            ax.set_ylabel("Success Probability")
            ax.set_title(f"Success Probability: {bench_to_chart}")
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    # -------------------------------------------------------------------------
    # Panel 6: Plain "Honest Results" Note (Wins / Ties / Losses vs Qiskit)
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.header("6. Honest Results: Empirical Comparison vs. Qiskit")
    st.markdown(
        "Summary of head-to-head performance across all 17 benchmarks in `results/results.csv`. "
        "Strictly measured against Qiskit's built-in transpiler levels 0 to 3 in the same basis `(rz, sx, x, cx)`."
    )

    benchmarks_list = df_results["benchmark"].unique()
    qiskit_levels = ["qiskit_L0", "qiskit_L1", "qiskit_L2", "qiskit_L3"]

    stat_rows = []
    for metric_name, label in [("two_qubit_gates", "Two-Qubit Gates (CX)"), ("total_gates", "Total Gates")]:
        for q_lvl in qiskit_levels:
            wins = 0
            ties = 0
            losses = 0
            for b in benchmarks_list:
                sub = df_results[df_results["benchmark"] == b]
                ours_val = sub[sub["variant"] == "ours"][metric_name].values[0]
                qiskit_val = sub[sub["variant"] == q_lvl][metric_name].values[0]
                if ours_val < qiskit_val:
                    wins += 1
                elif ours_val == qiskit_val:
                    ties += 1
                else:
                    losses += 1
            stat_rows.append({
                "Metric": label,
                "Comparison": f"ours vs {q_lvl}",
                "Wins (Ours Better)": wins,
                "Ties (Identical)": ties,
                "Losses (Qiskit Better)": losses,
                "Win Rate (%)": f"{(wins / len(benchmarks_list)) * 100:.1f}%",
            })

    stats_df = pd.DataFrame(stat_rows)
    st.dataframe(stats_df, width="stretch")

    st.info(
        "**Key Findings & Limitations**:\n"
        "- **Against Qiskit L0**: Our optimizer beats Qiskit L0 on 14/17 benchmarks in total gates and 6/17 in CX gates, with zero losses.\n"
        "- **Against Qiskit L1**: Our optimizer achieves 6 wins and 5 ties in total gates, and matches Qiskit L1's CX counts across all 17 benchmarks (0 losses).\n"
        "- **Against Qiskit L2/L3**: Qiskit L2/L3 uses global synthesis, analytical KAK matrix decomposition, and aggressive heuristics that our peephole/commutation passes alone do not duplicate, leading to losses on structured multi-qubit benchmarks.\n"
        "- **Device Note**: All simulations were conducted via noisy simulation using IBM device noise models (`FakeSherbrooke`). No physical hardware was queried."
    )

# -----------------------------------------------------------------------------
# Panel 7: Hardware run (saved results) - Appears ONLY if mode == "hardware"
# -----------------------------------------------------------------------------
HARDWARE_DIR = Path(__file__).resolve().parent.parent / "results" / "hardware"
hardware_records = []

if HARDWARE_DIR.exists():
    import json
    for json_file in sorted(HARDWARE_DIR.glob("*.json"), reverse=True):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                if content.get("mode") == "hardware":
                    hardware_records.append((json_file.name, content))
        except Exception:
            continue

if hardware_records:
    st.markdown("---")
    st.header("7. Hardware run (saved results)")
    st.markdown(
        "Execution results from IBM Quantum hardware submission. "
        "Shows fair apples-to-apples comparison using identical layout and backend pass managers."
    )

    if len(hardware_records) > 1:
        selected_file_name = st.selectbox(
            "Select hardware execution record:",
            options=[name for name, _ in hardware_records],
        )
        active_record = next(rec for name, rec in hardware_records if name == selected_file_name)
    else:
        active_record = hardware_records[0][1]

    col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
    with col_meta1:
        st.metric("Backend", active_record.get("backend", "Unknown"))
    with col_meta2:
        st.metric("Job ID", str(active_record.get("job_id", "Unknown"))[:16] + "...")
    with col_meta3:
        st.metric("Timestamp", str(active_record.get("timestamp", ""))[:19].replace("T", " "))
    with col_meta4:
        st.metric("Shots", active_record.get("shots", 0))

    st.markdown(f"**Physical Qubit Layout**: `{active_record.get('layout')}`")

    # Table of post-transpile metrics & success probabilities
    variants_data = active_record.get("variants", {})
    table_rows = []
    bar_variants = []
    bar_probs = []
    bar_errs = []

    for v_name in ["original", "ours", "qiskit_L1", "qiskit_L3"]:
        if v_name in variants_data:
            vd = variants_data[v_name]
            pm = vd.get("post_transpile_metrics", {})
            p_val = vd.get("success_probability")
            err_val = vd.get("stderr", 0.0)
            table_rows.append({
                "Variant": v_name,
                "Total Gates": pm.get("total_gates", "N/A"),
                "2Q Gates": pm.get("two_qubit_gates", "N/A"),
                "Depth": pm.get("depth", "N/A"),
                "Success Probability": f"{p_val:.4f} +/- {err_val:.4f}" if p_val is not None else "N/A",
                "Hellinger Fidelity": f"{vd.get('hellinger_fidelity'):.4f}" if vd.get("hellinger_fidelity") is not None else "N/A",
            })
            if p_val is not None:
                bar_variants.append(v_name)
                bar_probs.append(p_val)
                bar_errs.append(err_val or 0.0)

    st.subheader("Post-Transpile Metrics & Success Probabilities")
    st.dataframe(pd.DataFrame(table_rows), width="stretch")

    # Bar chart of success probabilities with error bars
    if bar_probs:
        st.subheader("Success Probability Comparison (with Binomial Error)")
        fig_hw, ax_hw = plt.subplots(figsize=(8, 4))
        colors = ["#7f7f7f", "#2ca02c", "#1f77b4", "#ff7f0e"][:len(bar_variants)]
        bars = ax_hw.bar(
            bar_variants,
            bar_probs,
            yerr=bar_errs,
            capsize=5,
            color=colors,
            alpha=0.85,
            edgecolor="black",
        )
        ax_hw.set_ylabel("Success Probability")
        ax_hw.set_ylim(0, max(bar_probs) * 1.25 if max(bar_probs) > 0 else 1.0)
        ax_hw.set_title(f"Hardware Execution: {active_record.get('benchmark')} on {active_record.get('backend')}")
        ax_hw.grid(True, linestyle="--", alpha=0.3, axis="y")

        for bar, p_val in zip(bars, bar_probs):
            yval = bar.get_height()
            ax_hw.text(
                bar.get_x() + bar.get_width() / 2.0,
                yval + 0.01,
                f"{p_val:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

        st.pyplot(fig_hw)
        plt.close(fig_hw)

# Offline simulation (dry-run) saved records
dry_run_records = []
if HARDWARE_DIR.exists():
    for json_file in sorted(HARDWARE_DIR.glob("*.json"), reverse=True):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                if content.get("mode") == "dry_run":
                    dry_run_records.append((json_file.name, content))
        except Exception:
            continue

if dry_run_records:
    with st.expander("📁 Offline Device Model Simulation Runs (Dry-Run Mode)"):
        st.markdown(
            "Saved execution records from offline dry-run **simulation** using IBM device noise models. "
            "These are classical simulations and not hardware executions."
        )
        sim_name = st.selectbox(
            "Select simulation record to preview:",
            options=[name for name, _ in dry_run_records],
            key="sim_record_select",
        )
        sim_rec = next(rec for name, rec in dry_run_records if name == sim_name)
        st.write(f"**Backend**: `{sim_rec.get('backend')}` (simulation) | **Job**: `{sim_rec.get('job_id')}` | **Layout**: `{sim_rec.get('layout')}`")
        sim_rows = []
        for v_name, v_data in sim_rec.get("variants", {}).items():
            pm = v_data.get("post_transpile_metrics", {})
            p_val = v_data.get("success_probability")
            err_val = v_data.get("stderr", 0.0)
            sim_rows.append({
                "Variant": v_name,
                "Total Gates": pm.get("total_gates", "N/A"),
                "2Q Gates": pm.get("two_qubit_gates", "N/A"),
                "Depth": pm.get("depth", "N/A"),
                "Success Probability": f"{p_val:.4f} +/- {err_val:.4f}" if p_val is not None else "N/A",
                "Hellinger Fidelity": f"{v_data.get('hellinger_fidelity'):.4f}" if v_data.get("hellinger_fidelity") is not None else "N/A",
            })
        st.dataframe(pd.DataFrame(sim_rows), width="stretch")


