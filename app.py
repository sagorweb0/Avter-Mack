import streamlit as st
import struct
import io
from PIL import Image
import texture2ddecoder
from astc_encoder import ASTCConfig, ASTCContext, ASTCImage, ASTCProfile, ASTCSwizzle, ASTCType

ASTC_MAGIC = 0x5CA1AB13

# ============================================================
# কোর ফাংশনগুলো (অপরিবর্তিত রাখা হয়েছে — লজিক একই আছে)
# ============================================================

# ASTC ফাইল থেকে তথ্য বের করার ফাংশন
def parse_astc(raw_bytes):
    if len(raw_bytes) < 16:
        raise ValueError("ফাইলটি খুব ছোট, বৈধ .astc ফাইল নয়")
    magic = struct.unpack("<I", raw_bytes[0:4])[0]
    if magic != ASTC_MAGIC:
        raise ValueError("বৈধ .astc ফাইল নয় (magic header মিলছে না)")
    block_x, block_y = raw_bytes[4], raw_bytes[5]

    def read24(off):
        return raw_bytes[off] | (raw_bytes[off + 1] << 8) | (raw_bytes[off + 2] << 16)

    width, height = read24(7), read24(10)
    blocks_x = -(-width // block_x)
    blocks_y = -(-height // block_y)
    needed = blocks_x * blocks_y * 16
    payload = raw_bytes[16:16 + needed]

    return width, height, block_x, block_y, payload


# ASTC থেকে সাধারণ ইমেজে (PNG) ডিকোড করার ফাংশন
def decode_astc_to_image(raw_bytes):
    width, height, block_x, block_y, payload = parse_astc(raw_bytes)
    decoded = texture2ddecoder.decode_astc(payload, width, height, block_x, block_y)
    img = Image.frombytes("RGBA", (width, height), decoded, "raw", "BGRA")
    # Unity-র জন্য উল্টানো থাকে, তাই ঠিক করা হচ্ছে
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return img, width, height, block_x, block_y


# সাধারণ ইমেজ (PNG) থেকে নতুন ASTC ফাইলে এনকোড করার ফাংশন
def encode_image_to_astc(img, block_x, block_y):
    # গেমের জন্য ছবিটিকে আবার উল্টে (bottom-up) দিতে হবে
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    img = img.convert("RGBA")

    # ASTC এনকোডারের কনফিগারেশন (Profile: LDR, Quality: 60)
    config = ASTCConfig(ASTCProfile.LDR, block_x, block_y, 1, 60.0, 0)
    context = ASTCContext(config)

    # PIL ইমেজকে ASTC ডেটায় কনভার্ট করা
    astc_img = ASTCImage(ASTCType.U8, img.width, img.height, data=img.tobytes())
    swizzle = ASTCSwizzle.from_str("RGBA")

    # ছবি কম্প্রেস করা (Payload তৈরি)
    comp_bytes = context.compress(astc_img, swizzle)

    # 16-বাইটের ASTC হেডার তৈরি করা
    magic = struct.pack("<I", 0x5CA1AB13)
    blocks = struct.pack("BBB", block_x, block_y, 1)

    def pack24(val):
        return struct.pack("BBB", val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xFF)

    header = magic + blocks + pack24(img.width) + pack24(img.height) + pack24(1)

    return header + comp_bytes


# ============================================================
# পেজ কনফিগারেশন
# ============================================================
st.set_page_config(
    page_title="ASTC Converter Pro",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# কাস্টম CSS — সাদা, পরিষ্কার, মডার্ন ডিজাইন
# ============================================================
st.markdown("""
<style>
    /* ---------- বেস কালার প্যালেট ---------- */
    :root {
        --accent: #2563eb;
        --accent-light: #eff6ff;
        --accent-dark: #1e40af;
        --text-main: #111827;
        --text-muted: #6b7280;
        --border-color: #e5e7eb;
        --bg-card: #ffffff;
        --bg-soft: #f9fafb;
    }

    html, body, [class*="css"] {
        font-family: "Segoe UI", "Hind Siliguri", "Noto Sans Bengali", sans-serif;
    }

    /* ---------- পুরো অ্যাপের ব্যাকগ্রাউন্ড ---------- */
    .stApp {
        background-color: #ffffff;
    }

    [data-testid="stHeader"] {
        background-color: rgba(255, 255, 255, 0.0);
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    /* ---------- হিরো হেডার ---------- */
    .hero-box {
        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
        border-radius: 18px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(37, 99, 235, 0.18);
    }
    .hero-title {
        color: #ffffff;
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .hero-sub {
        color: #dbeafe;
        font-size: 1rem;
        margin-top: 0.4rem;
        font-weight: 400;
    }

    /* ---------- ট্যাব স্টাইল ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: var(--bg-soft);
        padding: 6px;
        border-radius: 14px;
        border: 1px solid var(--border-color);
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 10px;
        padding: 0 22px;
        background-color: transparent;
        color: var(--text-muted);
        font-weight: 600;
        font-size: 0.98rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--accent) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
    }

    /* ---------- কার্ড কন্টেইনার ---------- */
    .card {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.3rem;
        margin-bottom: 1.3rem;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
        transition: box-shadow 0.2s ease;
    }
    .card:hover {
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--text-main);
        margin-bottom: 0.3rem;
    }
    .section-sub {
        color: var(--text-muted);
        font-size: 0.92rem;
        margin-bottom: 1.2rem;
    }

    /* ---------- ফাইল আপলোডার ---------- */
    [data-testid="stFileUploader"] {
        background-color: var(--bg-soft);
        border: 1.5px dashed #93c5fd;
        border-radius: 14px;
        padding: 0.8rem;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--accent);
    }

    /* ---------- বাটন ---------- */
    .stButton > button {
        background-color: var(--accent);
        color: #ffffff;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.4rem;
        font-weight: 600;
        transition: all 0.2s ease;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.2);
    }
    .stButton > button:hover {
        background-color: var(--accent-dark);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.3);
        transform: translateY(-1px);
    }

    .stDownloadButton > button {
        background-color: #ffffff;
        color: var(--accent);
        border: 1.5px solid var(--accent);
        border-radius: 10px;
        font-weight: 600;
        width: 100%;
        transition: all 0.2s ease;
    }
    .stDownloadButton > button:hover {
        background-color: var(--accent);
        color: #ffffff;
    }

    /* ---------- ইমেজ ফ্রেম ---------- */
    [data-testid="stImage"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--border-color);
    }
    [data-testid="stImage"] img {
        border-radius: 12px;
    }

    /* ---------- তথ্য ব্যাজ ---------- */
    .info-badge {
        display: inline-block;
        background-color: var(--accent-light);
        color: var(--accent-dark);
        font-size: 0.82rem;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 999px;
        margin-top: 0.4rem;
    }

    /* ---------- alert গুলোর কর্নার রাউন্ড ---------- */
    .stAlert {
        border-radius: 12px;
    }

    hr {
        border-color: var(--border-color);
    }

    /* ---------- ফুটার ---------- */
    .footer-note {
        text-align: center;
        color: var(--text-muted);
        font-size: 0.85rem;
        margin-top: 2.5rem;
        padding-top: 1.2rem;
        border-top: 1px solid var(--border-color);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# হিরো হেডার
# ============================================================
st.markdown("""
<div class="hero-box">
    <p class="hero-title">🖼️ ASTC Converter Pro</p>
    <p class="hero-sub">ASTC টেক্সচার ফাইলকে PNG-তে রূপান্তর করুন, অথবা নতুন ছবি দিয়ে রিপ্লেস করে নতুন ASTC ফাইল তৈরি করুন — দ্রুত ও সহজে।</p>
</div>
""", unsafe_allow_html=True)

# দুটি সেকশনের জন্য Tab তৈরি
tab1, tab2 = st.tabs(["📁 মাল্টিপল ফাইল কনভার্টার", "🔄 ফাইল রিপ্লেস এবং জেনারেট"])

# ============================================================
# সেকশন ১: একসাথে অনেক ফাইল আপলোড ও গ্রিড ভিউ
# ============================================================
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<p class="section-title">একাধিক ASTC ফাইলকে PNG করুন</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">একসাথে একাধিক .astc ফাইল আপলোড করুন, প্রতিটি ফাইল স্বয়ংক্রিয়ভাবে ছবিতে রূপান্তরিত হয়ে গ্রিড আকারে দেখা যাবে।</p>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "ASTC ফাইলগুলো সিলেক্ট করুন",
        accept_multiple_files=True,
        key="multi",
        label_visibility="visible",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_files:
        cols = st.columns(2)

        for idx, file in enumerate(uploaded_files):
            col = cols[idx % 2]
            with col:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                try:
                    img, w, h, bx, by = decode_astc_to_image(file.getvalue())
                    st.image(img, caption=file.name, use_container_width=True)
                    st.markdown(
                        f'<span class="info-badge">{w}×{h} px &nbsp;•&nbsp; ব্লক {bx}×{by}</span>',
                        unsafe_allow_html=True,
                    )

                    buf = io.BytesIO()
                    img.save(buf, format="PNG")

                    st.write("")
                    st.download_button(
                        label=f"⬇️ ডাউনলোড {file.name}.png",
                        data=buf.getvalue(),
                        file_name=f"{file.name.split('.')[0]}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"{file.name} প্রসেস করতে সমস্যা হয়েছে: {e}")
                st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# সেকশন ২: সিঙ্গেল ফাইল দেখা এবং রিপ্লেস করে আবার ASTC বানানো
# ============================================================
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<p class="section-title">ফাইল দেখুন এবং নতুন ইমেজ দিয়ে রিপ্লেস করুন</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">প্রথমে মূল .astc ফাইলটি আপলোড করুন, তারপর নতুন ছবি দিয়ে এটি রিপ্লেস করে নতুন ASTC ফাইল জেনারেট করুন।</p>', unsafe_allow_html=True)
    single_file = st.file_uploader("মূল ASTC ফাইল আপলোড করুন (বেস ফাইল)", key="single")
    st.markdown('</div>', unsafe_allow_html=True)

    if single_file:
        try:
            # মূল ফাইল ডিকোড করে সাইজ ও ব্লক চিনে রাখা
            original_img, orig_w, orig_h, bx, by = decode_astc_to_image(single_file.getvalue())

            col_a, col_b = st.columns([1, 1.2])
            with col_a:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<p class="section-title">মূল ছবি</p>', unsafe_allow_html=True)
                st.image(original_img, use_container_width=True)
                st.markdown(
                    f'<span class="info-badge">সাইজ: {orig_w}×{orig_h} &nbsp;•&nbsp; ব্লক: {bx}×{by}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown('</div>', unsafe_allow_html=True)

            with col_b:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown('<p class="section-title">ছবি রিপ্লেস করে নতুন ASTC ফাইল জেনারেট করুন</p>', unsafe_allow_html=True)

                replacement_file = st.file_uploader("নতুন ছবি (PNG/JPG) আপলোড করুন", type=['png', 'jpg', 'jpeg'])

                if replacement_file:
                    new_img = Image.open(replacement_file)
                    st.image(new_img, caption="আপনার নতুন ছবি", use_container_width=True)

                    # যদি সাইজ না মেলে, তাহলে ওয়ার্নিং দেওয়া
                    if new_img.size != (orig_w, orig_h):
                        st.warning(
                            f"⚠️ আপনার নতুন ছবির সাইজ ({new_img.width}x{new_img.height}) মূল ছবির সাইজের "
                            f"({orig_w}x{orig_h}) সাথে মিলছে না। কনভার্ট করার সময় এটি অটোমেটিক রিসাইজ হয়ে যাবে।"
                        )
                        new_img = new_img.resize((orig_w, orig_h))

                    if st.button("⚙️ নতুন ASTC ফাইল জেনারেট করুন", use_container_width=True):
                        with st.spinner('নতুন ফাইল তৈরি হচ্ছে, একটু অপেক্ষা করুন...'):
                            try:
                                # নতুন ছবিকে ASTC-তে এনকোড করা
                                new_astc_bytes = encode_image_to_astc(new_img, bx, by)

                                st.success("✅ নতুন ASTC ফাইল সফলভাবে তৈরি হয়েছে!")
                                st.download_button(
                                    label="⬇️ ডাউনলোড করুন (Modified ASTC)",
                                    data=new_astc_bytes,
                                    file_name=f"modified_{single_file.name}",
                                    mime="application/octet-stream",
                                    use_container_width=True,
                                )
                            except Exception as e:
                                st.error(f"জেনারেট করতে সমস্যা হয়েছে: {e}")
                st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"মূল ফাইলটি পড়তে সমস্যা হয়েছে: {e}")

# ============================================================
# ফুটার
# ============================================================
st.markdown('<div class="footer-note">ASTC Converter Pro · Streamlit দিয়ে তৈরি</div>', unsafe_allow_html=True)
