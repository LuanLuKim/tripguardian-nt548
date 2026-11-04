"""The mails the accounts send: plain data plus a text and an HTML body. No I/O."""

from dataclasses import dataclass
from html import escape

BRAND = "#b4532a"  # web/src/user/css/tokens.css --tg-brand; mail clients need literal colours


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    html: str


def reset_code_message(to: str, code: str, minutes: int) -> Message:
    """The one-time code for a password reset; no link, the code is typed into the page that asked for it."""
    spaced = f"{code[:3]} {code[3:]}"
    text = (f"Mã đặt lại mật khẩu TripGuardian của bạn là: {spaced}\n\n"
            f"Mã có hiệu lực trong {minutes} phút và chỉ dùng được một lần. Bạn nhập mã này vào trang đang mở để đặt mật khẩu mới.\n\n"
            "Nếu không phải bạn yêu cầu, hãy bỏ qua email này. Mật khẩu của bạn vẫn như cũ.\n"
            "Đừng chia sẻ mã này với bất kỳ ai, kể cả người nhắn là TripGuardian.\n\n"
            "TripGuardian\n")
    html = f"""<!doctype html>
<html lang="vi"><body style="margin:0;padding:24px 12px;background:#f6f6f6;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#111111">
<div style="max-width:480px;margin:0 auto;background:#ffffff;border:1px solid #e5e5e5;border-radius:16px;padding:32px 28px">
<p style="margin:0 0 20px;font-size:15px;font-weight:700;color:{BRAND}">TripGuardian</p>
<h1 style="margin:0 0 8px;font-size:20px;line-height:1.3">Mã đặt lại mật khẩu</h1>
<p style="margin:0 0 20px;font-size:15px;line-height:1.55;color:#444444">Bạn nhập mã này vào trang đang mở để đặt mật khẩu mới.</p>
<p style="margin:0 0 20px;padding:16px 0;text-align:center;font-size:36px;font-weight:700;letter-spacing:8px;background:#f6f6f6;border-radius:12px;font-family:'SF Mono',Menlo,Consolas,monospace">{escape(spaced)}</p>
<p style="margin:0 0 12px;font-size:14px;line-height:1.55;color:#444444">Mã có hiệu lực trong <strong>{minutes} phút</strong> và chỉ dùng được một lần.</p>
<p style="margin:0 0 12px;font-size:14px;line-height:1.55;color:#444444">Nếu không phải bạn yêu cầu, hãy bỏ qua email này. Mật khẩu của bạn vẫn như cũ.</p>
<p style="margin:0;font-size:13px;line-height:1.55;color:#6b6b6b">Đừng chia sẻ mã này với bất kỳ ai, kể cả người nhắn là TripGuardian.</p>
</div></body></html>"""
    return Message(to=to, subject=f"{code} là mã đặt lại mật khẩu TripGuardian", text=text, html=html)
