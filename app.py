# -*- coding: utf-8 -*-
"""
차종마스터 로컬 서버 — 5단계 트리 뷰어/관리 UI
  python app.py            # http://localhost:8777
정적 JSON(data/vehicle-tree.json)이 SSOT. 없으면 체크포인트를 실시간 병합해
크롤 진행 중에도 채워지는 걸 볼 수 있다.
"""
import os, json, re, http.server, socketserver

# 트림(BadgeDetail)에서 파워트레인 토큰 제거 → 순수 등급명 (crawl_encar.normalize_trim 과 동일)
_TRIM_STRIP = re.compile(
    r"\b\d+인승\b"
    r"|\b\d\.\d\b"
    r"|터보|turbo|t-?gdi"
    r"|가솔린|디젤|lpg|전기|하이브리드|hev|phev"
    r"|2wd|4wd|awd|xdrive|4matic|콰트로|quattro|4모션|4motion",
    re.IGNORECASE)

def normalize_trim(raw):
    s = _TRIM_STRIP.sub(" ", raw or "")
    return re.sub(r"\s+", " ", s).strip(" ·-") or "기본"

def clean_trims(trims):
    seen, out = set(), []
    for t in trims:
        raw = t.get("name")
        n = normalize_trim(raw)
        if n in seen:
            continue
        seen.add(n)
        out.append({"name": n, "raw": raw} if n != raw else {"name": n})
    return out

EV_FUELS = ("전기", "수소")

def finalize_powertrains(pws):
    """EV는 배기량 제거 후 동일 사양 병합, 트림 정규화 (crawl_encar 와 동일)."""
    groups, order = {}, []
    for p in pws or []:
        fuel = p.get("fuel")
        disp, displ = p.get("displacement"), p.get("displacement_l")
        if fuel in EV_FUELS:
            disp = displ = None
        key = (fuel, displ, p.get("turbo"), p.get("seat"), p.get("drivetrain"))
        if key not in groups:
            groups[key] = {"fuel": fuel, "displacement": disp, "displacement_l": displ,
                           "turbo": p.get("turbo"), "seat": p.get("seat"),
                           "drivetrain": p.get("drivetrain"), "trims": []}
            order.append(key)
        groups[key]["trims"].extend(p.get("trims", []))
    out = []
    for key in order:
        g = groups[key]
        g["trims"] = clean_trims(g["trims"])
        out.append(g)
    return out

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CKPT = os.path.join(DATA, "checkpoints")
PUBLIC = os.path.join(HERE, "public")
PORT = 8777

CARTYPE = {"Y": "국산", "N": "수입"}

def _strip(node):
    node.pop("_action", None)
    for k in ("models", "sub_models", "powertrains", "trims"):
        if isinstance(node.get(k), list):
            for c in node[k]:
                _strip(c)
    return node

def sort_tree(tree):
    """제조사: 국산 먼저·매물순 / 모델: 매물순 / 세부모델: 출시순(최신 위)."""
    tree["manufacturers"].sort(key=lambda m: (0 if m.get("car_type") == "국산" else 1,
                                              -(m.get("count") or 0)))
    for m in tree["manufacturers"]:
        m.get("models", []).sort(key=lambda g: -(g.get("count") or 0))
        for g in m.get("models", []):
            g.get("sub_models", []).sort(key=lambda s: (s.get("start") or "000000"), reverse=True)
    return tree

def build_tree():
    """완성본이 있으면 그대로, 없으면 체크포인트 실시간 병합."""
    final = os.path.join(DATA, "vehicle-tree.json")
    if os.path.exists(final):
        with open(final, encoding="utf-8") as f:
            return json.load(f)
    mans = []
    if os.path.isdir(CKPT):
        for fn in sorted(os.listdir(CKPT)):
            if not fn.endswith(".json"):
                continue
            ct = fn.split("_")[0]
            try:
                with open(os.path.join(CKPT, fn), encoding="utf-8") as f:
                    node = _strip(json.load(f))
            except (ValueError, OSError):
                continue  # 크롤이 쓰는 중일 수 있음
            node.setdefault("car_type", CARTYPE.get(ct, ct))
            for g in node.get("models", []):
                for s in g.get("sub_models", []):
                    if s.get("powertrains"):
                        s["powertrains"] = finalize_powertrains(s["powertrains"])
            mans.append(node)
    tree = {"source": "encar", "live": True,
            "levels": ["제조사", "모델", "세부모델", "파워트레인", "세부트림"],
            "manufacturers": mans}
    return sort_tree(tree)

def stats(tree):
    mg = sm = pw = tr = 0
    for m in tree.get("manufacturers", []):
        for g in m.get("models", []):
            mg += 1
            for s in g.get("sub_models", []):
                sm += 1
                for p in s.get("powertrains", []):
                    pw += 1
                    tr += len(p.get("trims", []))
    return {"manufacturers": len(tree.get("manufacturers", [])),
            "models": mg, "sub_models": sm, "powertrains": pw, "trims": tr,
            "live": tree.get("live", False)}

class H(http.server.BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")  # 새로고침 시 항상 최신
        self.send_header("Access-Control-Allow-Origin", "*")  # 타 ERP 참조 허용
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "/index.html":
            with open(os.path.join(PUBLIC, "index.html"), encoding="utf-8") as f:
                self._send(f.read(), "text/html; charset=utf-8")
        elif path == "/api/tree":
            self._send(json.dumps(build_tree(), ensure_ascii=False))
        elif path == "/api/stats":
            self._send(json.dumps(stats(build_tree()), ensure_ascii=False))
        else:
            self._send('{"error":"not found"}', code=404)

    def log_message(self, *a):
        pass  # 조용히

if __name__ == "__main__":
    os.makedirs(PUBLIC, exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd:
        print("차종마스터 → http://localhost:%d" % PORT)
        httpd.serve_forever()
