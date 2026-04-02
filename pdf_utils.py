from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_pdf(user, report_data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"EPL Report for {user.username}")
    y -= 30

    c.setFont("Helvetica", 12)

    # Half-time results
    if 'half_time' in report_data:
        c.drawString(50, y, "🏁 Half-Time Results:")
        y -= 20
        for match in report_data['half_time']:
            c.drawString(60, y, f"{match['home']} {match['home_goals']} - {match['away_goals']} {match['away']}")
            y -= 15
        y -= 10

    # Full-time results
    if 'full_time' in report_data:
        c.drawString(50, y, "⚽ Full-Time Results:")
        y -= 20
        for match in report_data['full_time']:
            c.drawString(60, y, f"{match['home']} {match['home_goals']} - {match['away_goals']} {match['away']}")
            y -= 15
        y -= 10

    # Match Insights
    if 'match_insights' in report_data:
        c.drawString(50, y, "📊 Match Insights:")
        y -= 20
        for insight in report_data['match_insights']:
            c.drawString(60, y, f"{insight['team']}: Played {insight['played']}, Wins {insight['wins']}, Draws {insight['draws']}, Losses {insight['losses']}")
            y -= 15
        y -= 10

    # Fixtures
    if 'fixtures' in report_data:
        c.drawString(50, y, "📅 Upcoming Fixtures:")
        y -= 20
        for fixture in report_data['fixtures']:
            c.drawString(60, y, f"{fixture['date']}: {fixture['home']} vs {fixture['away']}")
            y -= 15

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
