import streamlit as st
from PIL import Image
import numpy as np
import zipfile
import io
import cv2
import os

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Mockup Generator", layout="centered")

st.title("👕 Minimal Mockup Generator")
st.caption("Batch generate clean product mockups (fast & consistent)")

# ---------------- PRESETS ----------------
TEMPLATE_PROFILES = {
    "plain": {"padding": 0.45, "offset": 23},
    "model": {"padding": 0.45, "offset": 38}
}

# ---------------- SIDEBAR ----------------
st.sidebar.header("⚙️ Controls")

padding_override = st.sidebar.slider("Padding Override", 0.2, 1.2, 1.0, 0.05)
vertical_shift = st.sidebar.slider("Vertical Fine Adjust", -200, 200, 0)
horizontal_shift = st.sidebar.slider("Horizontal Shift", -200, 200, 0)
scale_override = st.sidebar.slider("Scale Override", 0.5, 1.5, 1.0)

variation_count = st.sidebar.slider("Variations per Design", 1, 5, 1)

# ---------------- CACHE ----------------
@st.cache_data
def load_image(file_bytes):
    return Image.open(io.BytesIO(file_bytes)).convert("RGBA")

@st.cache_data
def get_shirt_bbox_cached(image_array):
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        return cv2.boundingRect(largest)
    return None

# ---------------- UPLOAD ----------------
st.markdown("## 📤 Upload")

design_files = st.file_uploader(
    "Design Images",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

shirt_files = st.file_uploader(
    "Shirt Templates (use naming: black_plain.png, white_model.png)",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

# ---------------- NAMING ----------------
design_names = {}
if design_files:
    st.markdown("## ✏️ Name Designs")
    for file in design_files:
        default = os.path.splitext(file.name)[0]
        design_names[file.name] = st.text_input(file.name, value=default)

# ---------------- PREVIEW ----------------
if design_files and shirt_files:
    st.markdown("## 👀 Preview")

    selected_design = st.selectbox("Design", design_files, format_func=lambda x: x.name)
    selected_shirt = st.selectbox("Template", shirt_files, format_func=lambda x: x.name)

    # load images
    design = load_image(selected_design.read())
    shirt = load_image(selected_shirt.read())

    # detect type
    parts = selected_shirt.name.lower().split("_")
    template_type = parts[1] if len(parts) > 1 else "plain"

    preset = TEMPLATE_PROFILES.get(template_type, TEMPLATE_PROFILES["plain"])

    padding = preset["padding"] * padding_override
    offset_pct = preset["offset"]

    img_cv = np.array(shirt.convert("RGB"))[:, :, ::-1]
    bbox = get_shirt_bbox_cached(img_cv)

    if bbox:
        sx, sy, sw, sh = bbox
        scale = min(sw / design.width, sh / design.height, 1.0)
        scale *= padding * scale_override

        new_w = int(design.width * scale)
        new_h = int(design.height * scale)

        resized = design.resize((new_w, new_h))

        x = sx + (sw - new_w) // 2 + horizontal_shift
        y = sy + int(sh * offset_pct / 100) + vertical_shift
    else:
        resized = design
        x = (shirt.width - design.width) // 2
        y = (shirt.height - design.height) // 2

    preview = shirt.copy()
    preview.paste(resized, (x, y), resized)

    st.image(preview, use_container_width=True)

# ---------------- GENERATE ----------------
if st.button("🚀 Generate Mockups"):
    if not (design_files and shirt_files):
        st.warning("Upload designs and templates")
    else:
        progress = st.progress(0)

        master_zip = io.BytesIO()

        with zipfile.ZipFile(master_zip, "w", zipfile.ZIP_DEFLATED) as master_zipf:

            total = len(design_files)

            for i, design_file in enumerate(design_files):

                design = load_image(design_file.read())
                name = design_names.get(design_file.name, "design")

                inner_zip_buffer = io.BytesIO()

                with zipfile.ZipFile(inner_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:

                    for shirt_file in shirt_files:

                        shirt = load_image(shirt_file.read())

                        parts = shirt_file.name.lower().split("_")
                        template_type = parts[1] if len(parts) > 1 else "plain"
                        color = parts[0]

                        preset = TEMPLATE_PROFILES.get(template_type, TEMPLATE_PROFILES["plain"])

                        padding = preset["padding"] * padding_override
                        offset_pct = preset["offset"]

                        img_cv = np.array(shirt.convert("RGB"))[:, :, ::-1]
                        bbox = get_shirt_bbox_cached(img_cv)

                        for v in range(variation_count):

                            shirt_copy = shirt.copy()

                            if bbox:
                                sx, sy, sw, sh = bbox

                                scale = min(sw / design.width, sh / design.height, 1.0)
                                scale *= padding * scale_override

                                # slight variation
                                scale *= (1 + (v * 0.05))

                                new_w = int(design.width * scale)
                                new_h = int(design.height * scale)

                                resized = design.resize((new_w, new_h))

                                x = sx + (sw - new_w) // 2 + horizontal_shift
                                y = sy + int(sh * offset_pct / 100) + vertical_shift + (v * 5)

                            else:
                                resized = design
                                x = (shirt.width - design.width) // 2
                                y = (shirt.height - design.height) // 2

                            shirt_copy.paste(resized, (x, y), resized)

                            rgb = shirt_copy.convert("RGB")

                            img_bytes = io.BytesIO()
                            rgb.save(img_bytes, format="JPEG", quality=90, optimize=True)
                            img_bytes.seek(0)

                            filename = f"{name}_{color}_{template_type}_v{v+1}.jpg"

                            zipf.writestr(filename, img_bytes.getvalue())

                inner_zip_buffer.seek(0)
                master_zipf.writestr(f"{name}.zip", inner_zip_buffer.read())

                progress.progress((i + 1) / total)

        master_zip.seek(0)

        st.download_button(
            "📦 Download All Mockups",
            data=master_zip,
            file_name="mockups_bundle.zip",
            mime="application/zip"
        )
