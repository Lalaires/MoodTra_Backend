import os

def prepare_runtime_tmp():
    dirs = [
        os.getenv("HOME"),
        os.getenv("HF_HOME"),
        os.getenv("TRANSFORMERS_CACHE"),
        os.getenv("XDG_CACHE_HOME"),
        os.getenv("TORCH_HOME"),
        os.getenv("NLTK_DATA"),
        os.getenv("MPLCONFIGDIR"),
        os.getenv("NUMBA_CACHE_DIR"),
    ]
    for d in filter(None, dirs):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            print(f"Skip creating {d}: {e}")