"""
Visitor Counter Router
Sesuai dengan tabel visitor_counter yang baru:
  - kolom: visit_date, visit_count  (bukan visitor_count)
  - fungsi: increment_visitor()
  - fungsi: get_visitor_stats() → { today, this_month, all_time }
"""

from fastapi import APIRouter, HTTPException
from datetime import date
from app.database import database

router = APIRouter(
    prefix="/api/visitor-count",
    tags=["Visitor Counter"]
)


@router.post("/increment")
async def increment_visitor():
    """
    Increment today's visitor count by 1.
    Pakai fungsi increment_visitor() yang sudah di-setup di Supabase.
    """
    try:
        await database.execute("SELECT increment_visitor()")
        row = await database.fetch_one(
            "SELECT visit_count FROM visitor_counter WHERE visit_date = CURRENT_DATE"
        )
        count = row["visit_count"] if row else 0
        return {"count": count, "date": str(date.today())}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/stats")
async def get_visitor_stats():
    """
    Get all visitor stats sekaligus:
    - today      : pengunjung hari ini
    - this_month : pengunjung bulan ini
    - all_time   : total semua waktu
    Pakai fungsi get_visitor_stats() dari Supabase.
    """
    try:
        row = await database.fetch_one("SELECT * FROM get_visitor_stats()")
        return {
            "today":      row["today"]      if row else 0,
            "this_month": row["this_month"] if row else 0,
            "all_time":   row["all_time"]   if row else 0,
            "date":       str(date.today()),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("")
async def get_today_count():
    """Get today's visitor count only."""
    try:
        row = await database.fetch_one(
            "SELECT visit_count FROM visitor_counter WHERE visit_date = CURRENT_DATE"
        )
        count = row["visit_count"] if row else 0
        return {"count": count, "date": str(date.today())}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/total")
async def get_total_visitors():
    """Get total visitors across all dates."""
    try:
        row = await database.fetch_one(
            "SELECT COALESCE(SUM(visit_count), 0) AS total FROM visitor_counter"
        )
        return {"total": row["total"] if row else 0}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/stats/weekly")
async def get_weekly_stats():
    """Get visitor stats for the last 7 days."""
    try:
        rows = await database.fetch_all("""
            SELECT visit_date, visit_count
            FROM visitor_counter
            WHERE visit_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY visit_date DESC
        """)
        data  = [{"date": str(row["visit_date"]), "count": row["visit_count"]} for row in rows]
        total = sum(r["count"] for r in data)
        return {"data": data, "total": total}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")