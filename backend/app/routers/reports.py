"""PDF report export — an executive analytics summary for a topic."""
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Topic
from ..services import insights

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/pdf")
def pdf_report(topic_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    topic = db.get(Topic, topic_id) if topic_id else None
    tname = topic.name if topic else "All topics"
    health = insights.brand_health(db, topic_id, min(days, 14))
    crisis = insights.crisis(db, topic_id, min(days, 14))
    ov = insights.brand_health  # reuse scope for counts below
    from sqlalchemy import func
    from ..models import Post
    q = db.query(Post).filter(Post.is_hidden.is_(False))
    if topic_id:
        q = q.filter(Post.topic_id == topic_id)
    total = q.count()
    by_sent = dict(q.with_entities(Post.sentiment, func.count()).group_by(Post.sentiment).all())
    by_platform = q.with_entities(Post.platform, func.count()).group_by(Post.platform) \
        .order_by(func.count().desc()).limit(10).all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("CrawlOps — Media Intelligence Report", styles["Title"]))
    story.append(Paragraph(f"Topic: <b>{tname}</b> · Window: last {days} days · "
                           f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    kpi = [["Mentions", str(total)],
           ["Brand Health", f"{health['score']} ({health['grade']})"],
           ["Crisis Risk", f"{crisis['risk']} ({crisis['level']})"],
           ["Positive", str(by_sent.get("pos", 0))],
           ["Neutral", str(by_sent.get("neu", 0))],
           ["Negative", str(by_sent.get("neg", 0))]]
    t = Table(kpi, colWidths=[60 * mm, 100 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f9f9f7")),
                           ("FONTSIZE", (0, 0), (-1, -1), 10),
                           ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0b0b0b"))]))
    story.append(Paragraph("Summary", styles["Heading2"]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Brand Health components", styles["Heading2"]))
    comp = [["Component", "Score"]] + [[k.title(), str(v)] for k, v in health["components"].items()]
    ct = Table(comp, colWidths=[80 * mm, 40 * mm])
    ct.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a78d6")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    story.append(ct)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Volume by platform", styles["Heading2"]))
    pt = [["Platform", "Mentions"]] + [[p, str(c)] for p, c in by_platform]
    ptab = Table(pt, colWidths=[80 * mm, 40 * mm])
    ptab.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
                              ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b0b0b")),
                              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                              ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    story.append(ptab)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("<font size=8 color='#898781'>EMV and reach are conservative estimates "
                           "(see Settings → CPM). Sentiment/emotion require an enabled AI provider.</font>",
                           styles["Normal"]))

    doc.build(story)
    buf.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    fn = f"crawlops-report-{stamp}.pdf"
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={fn}"})
