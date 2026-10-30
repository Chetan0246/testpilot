"""Streamlit demo: paste or upload a Python module, watch TestPilot test it live."""
import tempfile
from pathlib import Path

import streamlit as st

from testpilot import agent
from testpilot.llm import NemotronClient

st.set_page_config(page_title="TestPilot", page_icon="🧪", layout="wide")
st.title("🧪 TestPilot")
st.caption("Writes, runs and repairs pytest suites with NVIDIA Nemotron on Nebius Token Factory.")

sample = Path(__file__).parent / "examples" / "inventory.py"
with st.sidebar:
    api_key = st.text_input("Nebius API key", type="password",
                            help="Leave blank to use the NEBIUS_API_KEY environment variable.")
    rounds = st.slider("Max repair rounds", 1, 5, 3)
    st.markdown("Fast model drafts and triages; the stronger Nemotron model steps in on the last repair.")

uploaded = st.file_uploader("Upload a .py file", type="py")
default = uploaded.getvalue().decode() if uploaded else sample.read_text()
name = uploaded.name if uploaded else "inventory.py"
code = st.text_area("Module under test", default, height=320)

if st.button("Run TestPilot", type="primary"):
    try:
        llm = NemotronClient(api_key=api_key or None)
    except RuntimeError as e:
        st.error(str(e))
        st.stop()
    tmp = Path(tempfile.mkdtemp()) / name
    tmp.write_text(code)
    log = st.status("TestPilot is working ...", expanded=True)
    report = agent.run(tmp, llm, max_rounds=rounds, on_event=log.write)
    log.update(label="Done" if report.success else "Finished with failures",
               state="complete" if report.success else "error")

    last = report.rounds[-1].result
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Passed", last.passed)
    c2.metric("Failed", last.failed + last.errors)
    c3.metric("Coverage", f"{last.coverage:.0f}%" if last.coverage is not None else "n/a")
    c4.metric("Nemotron calls", llm.usage.calls)

    if report.bugs:
        st.subheader("🐞 Likely bugs in your code")
        for b in report.bugs:
            st.markdown(f"- **{b['test']}**: {b['reason']}")
    else:
        st.success("No bugs flagged in your code.")

    st.subheader("Generated tests")
    st.code(report.test_code, language="python")
    st.download_button("Download test file", report.test_code, file_name=f"test_{Path(name).stem}.py")
