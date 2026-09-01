"""CSS for the self-contained HTML report."""


def dashboard_css() -> str:
    return """*{box-sizing:border-box}body{margin:0;background:#f8fafc;color:#172033;font:15px system-ui}
header,main,footer{max-width:1200px;margin:auto}header{padding:36px 24px 20px;display:flex;justify-content:space-between}
h1{margin:.1rem 0;font-size:2rem}h2{margin-top:0}.eyebrow{color:#2563eb;font-weight:700;text-transform:uppercase}
.status{background:#dbeafe;color:#1d4ed8;padding:8px 14px;border-radius:999px;height:max-content}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;background:none;padding:0}
.cards article,section{background:white;border:1px solid #e2e8f0;border-radius:14px;padding:20px}.cards strong{display:block;font-size:1.65rem;margin:7px 0}.cards span,.cards small,.muted,.note{color:#64748b}
main{padding:0 24px;display:grid;gap:18px}.split{display:grid;grid-template-columns:1fr 1fr;gap:24px}pre{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;padding:14px;border-radius:9px;overflow:auto}
.table{overflow:auto}table{border-collapse:collapse;width:100%}th,td{padding:9px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top}code{font-size:12px}.hbar{display:flex;align-items:center;gap:8px;margin:9px 0}.hbar span{width:25%;overflow:hidden;text-overflow:ellipsis}.hbar i{display:block;height:13px;background:#2563eb;border-radius:5px}.hbar i.bad{background:#dc2626}.hbar b{white-space:nowrap}.warning{padding:12px;background:#fef2f2;color:#991b1b;border-radius:8px}svg{width:100%;max-height:310px}circle{fill:#2563eb}.definitions{display:grid;grid-template-columns:max-content 1fr;gap:8px 18px}.definitions dt{font-weight:700}.definitions dd{margin:0}footer{padding:28px;color:#64748b}@media(max-width:800px){.cards,.split{grid-template-columns:1fr 1fr}}@media(max-width:520px){.cards,.split{grid-template-columns:1fr}.definitions{grid-template-columns:1fr}}"""
