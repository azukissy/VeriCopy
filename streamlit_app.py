import os
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from vericopy import verify


WINDOWS_CSS = """
<style>
body {
    background-color: #eff3f6;
}
section.main {
    background-color: #f7f9fb;
    border-radius: 16px;
    padding: 1.5rem 2rem;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}
header, div[data-testid="stToolbar"] {
    background: linear-gradient(180deg, #ffffff 0%, #f1f3f5 100%);
}
.stButton>button {
    background-color: #0078d4;
    color: #ffffff;
    border-radius: 4px;
    border: 1px solid #005a9e;
}
.stButton>button:hover {
    background-color: #106ebe;
}
.stTextInput>div>div>input,
.stSelectbox>div>div>div>div>select,
.stNumberInput>div>div>input {
    border-radius: 4px;
    border: 1px solid #c8ccd0;
    background-color: #ffffff;
    color: #1f2937 !important;
    -webkit-text-fill-color: #1f2937;
}
.css-1d391kg {
    box-shadow: none;
}
</style>
"""


def format_file_list(items: List[str]) -> List[Dict[str, Any]]:
    return [{'File Name': item} for item in sorted(items)]


def render_summary(result: Dict[str, Any]) -> None:
    cols = st.columns(3)
    cols[0].metric("Matched", result.get('matched_count', 0), delta=None)
    cols[1].metric("Not Matched", result.get('not_matched_count', 0), delta=None)
    cols[2].metric("Log File", Path(result.get('log_file_path', '')).name if result.get('log_file_path') else "n/a")

    if result.get('not_matched_files'):
        st.markdown("### Not Matched Files")
        st.table(result['not_matched_files'])


def main() -> None:
    st.set_page_config(page_title="VeriCopy GUI", page_icon="🪟", layout="wide")
    st.markdown(WINDOWS_CSS, unsafe_allow_html=True)

    st.title("VeriCopy GUI")
    st.write("Windows風のUIで入力と出力のファイル検証を実行します。")

    with st.sidebar:
        st.header("Settings")
        input_dir = st.text_input("Input folder", "input")
        output_dir = st.text_input("Output folder", "output")
        log_dir = st.text_input("Log folder", "logs")
        algorithm = st.selectbox(
            "Hash algorithm",
            [
                "sha256",
                "sha512",
                "sha3_256",
                "sha3_512",
                "md5",
                "sha1",
            ],
            index=1,
        )
        chunk_size_mb = st.number_input("Chunk size (MiB)", min_value=1, max_value=128, value=16)
        enable_parallel = st.checkbox("Parallel drive verification", value=True)
        st.markdown("---")
        st.write("Streamlit 内でログを生成し、指定のログフォルダに保存します。")

    if st.button("Verify Files"):
        if not os.path.isdir(input_dir):
            st.error(f"入力ディレクトリが見つかりません: {input_dir}")
            return
        if not os.path.isdir(output_dir):
            st.error(f"出力ディレクトリが見つかりません: {output_dir}")
            return

        progress_area = st.empty()
        log_lines: List[str] = []

        def logger(message: str) -> None:
            log_lines.append(message)
            progress_area.text("\n".join(log_lines[-20:]))

        with st.spinner("Verification in progress..."):
            result = verify(
                input_dir,
                output_dir,
                algorithm=algorithm,
                chunk_size=int(chunk_size_mb * 1024 * 1024),
                enable_parallel_drives=enable_parallel,
                log_dir=log_dir,
                logger=logger,
            )

        st.success("Verification completed")
        render_summary(result)
        st.markdown("### Log Preview")
        st.text_area("Verification log", value="\n".join(log_lines), height=280)

    st.markdown("---")
    st.write("VeriCopy GUI は Streamlit ベースの Windows ライクなデザインで、フォルダの整合性を簡単に確認できます。")


if __name__ == "__main__":
    main()
