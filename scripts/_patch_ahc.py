"""一次性：把 _cluster_neural 从谱聚类改回 AHC。"""
import re
from pathlib import Path

p = Path(r"F:\python-exercise\Industrial_LLM\langchain-learn\Memora\memora\whisper\diarize.py")
t = p.read_text(encoding="utf-8")

new_func = '''def _cluster_neural(E: np.ndarray, num_speakers: int
                    ) -> tuple[np.ndarray, int]:
    """平均链接凝聚聚类（AHC，CAM++ embedding）；num_speakers=0 按相似度阈值。

    声纹与 whisper 句子段解耦：先按 VAD 短窗提 embedding，再 AHC + cosine
    阈值自动定人数。选 AHC 而非谱聚类：真实近场会议中，谱聚类在"快速轮流"
    段（大量混合窗）会退化到 k=1、信息丢失；AHC 宁可过分割（每位主导者保留
    独立簇，用户可在界面合并），也不把不同人并成一人。
    """
    n = len(E)
    if n < 2:
        return np.zeros(n, dtype=int), 1
    if num_speakers and num_speakers > 0:
        k = max(1, min(num_speakers, n))
        if k == 1:
            return np.zeros(n, dtype=int), 1
        lab = AgglomerativeClustering(n_clusters=k, metric="cosine",
                                      linkage="average").fit_predict(E)
        return lab, k
    # 自动 k：平均链接 + cosine 相似度阈值
    ac = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average",
        distance_threshold=1.0 - config.SPEAKER_SIM_THRESHOLD)
    lab = ac.fit_predict(E)
    return lab, len(set(lab.tolist()))


'''

# 定位从 def _cluster_neural 到 def _assign_segments
pat = re.compile(r"def _cluster_neural\(.*?\n(?=def _assign_segments)", re.S)
t2, cnt = pat.subn(new_func, t)
assert cnt == 1, f"替换次数 {cnt}"
p.write_text(t2, encoding="utf-8")
print("replaced _cluster_neural -> AHC")
