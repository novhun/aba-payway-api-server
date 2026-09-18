import os
import base64
import io
import qrcode
from PIL import Image, ImageDraw

def parse_khqr_merchant_name(khqr_str: str) -> str:
    """Parses EMVCo layout sequences to extract Tag 59 (Merchant Name) value."""
    try:
        idx = 0
        while idx < len(khqr_str):
            tag = khqr_str[idx:idx+2]
            length = int(khqr_str[idx+2:idx+4])
            value = khqr_str[idx+4:idx+4+length]
            if tag == "59":
                return value
            idx += 4 + length
    except Exception:
        pass
    return "KHQR MERCHANT"

def generate_qr_image(text: str) -> Image.Image:
    """Generates an EMVCo QR code and stitches 'khqr_icon.png' into the center."""
    ICON_FILENAME = "khqr_icon.png"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High ceiling required for center overlays
        box_size=10,
        border=1,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = img_qr.size

    if os.path.exists(ICON_FILENAME):
        try:
            icon = Image.open(ICON_FILENAME)
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')

            # Scale logo to ~22% of total canvas real-estate to maintain scannability
            logo_width_max = int(qr_width * 0.22)
            aspect_ratio = icon.size[1] / icon.size[0]
            logo_height = int(logo_width_max * aspect_ratio)
            icon = icon.resize((logo_width_max, logo_height), Image.Resampling.LANCZOS)
            
            # Draw a white circle frame behind the logo
            circle_radius = int(max(logo_width_max, logo_height) / 2 * 1.25)
            center_x, center_y = qr_width // 2, qr_height // 2
            
            draw = ImageDraw.Draw(img_qr)
            draw.ellipse(
                (center_x - circle_radius, center_y - circle_radius, 
                 center_x + circle_radius, center_y + circle_radius),
                fill="white"
            )
            
            # Position offset calculation coordinates
            position = (
                (qr_width - icon.size[0]) // 2,
                (qr_height - icon.size[1]) // 2
            )
            img_qr.paste(icon, position, icon)
        except Exception as e:
            print(f"WARN: Failed blending center logo: {str(e)}")
    else:
        print(f"WARN: '{ICON_FILENAME}' missing. Generating standard canvas model.")

    return img_qr

def generate_qr_bytes(text: str) -> bytes:
    """Returns raw binary PNG bytes for direct download/attachment."""
    img_qr = generate_qr_image(text)
    buffered = io.BytesIO()
    img_qr.save(buffered, format="PNG")
    return buffered.getvalue()

def generate_qr_base64(text: str) -> str:
    """Returns data:image/png;base64 string for inline HTML <img> display."""
    qr_bytes = generate_qr_bytes(text)
    qr_base64 = base64.b64encode(qr_bytes).decode("utf-8")
    return f"data:image/png;base64,{qr_base64}"

