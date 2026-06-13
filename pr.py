import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# Səhifənin tənzimləmələri
st.set_page_config(page_title="Nazirlik PR Generator", page_icon="📝", layout="wide")

# ====================================================================
# 1. AI MODELİNİN AYARLANMASI (STREAMLIT CLOUD SECRETS İLƏ)
# ====================================================================
model = None
api_status = False

try:
    # Buluddakı Secrets bölməsindən açarı çəkirik
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    api_status = True
except Exception:
    st.warning(
        "⚠️ API Key tapılmadı! Zəhmət olmasa Streamlit Cloud-un 'Advanced Settings -> Secrets' bölməsində GOOGLE_API_KEY parametrini düzgün qeyd etdiyinizdən əmin olun.")


# ====================================================================
# 2. VEB SAYTDAN MƏLUMAT ÇƏKMƏ (RAG)
# ====================================================================
@st.cache_data(ttl=3600)
def fetch_news_context():
    url = "https://sosial.gov.az/az/media/xeberler"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        news_items = []
        for p in soup.find_all(['h3', 'h4', 'p'], limit=30):
            text = p.get_text(strip=True)
            if len(text) > 40:
                news_items.append(text)

        return " ".join(news_items)
    except Exception as e:
        return f"Xəbərləri çəkmək mümkün olmadı. Səbəb: {e}"


# ====================================================================
# 3. İNTERFEYS VƏ DİZAYN
# ====================================================================
st.title("📝 Süni İntellektlə Press-Reliz Generatoru")
st.markdown("Əmək və Əhalinin Sosial Müdafiəsi Nazirliyinin rəsmi üslubuna uyğun press-relizlərin avtomatik yazılması.")
st.divider()

# Yan panel
with st.sidebar:
    st.header("⚙️ Məlumat")
    st.info("Sistem avtomatik olaraq sosial.gov.az saytındakı xəbərləri analiz edərək yeni mətn yaradır.")
    if api_status:
        st.success("✅ Sistem Süni İntellektə uğurla qoşulub (Bulud).")
    else:
        st.error("❌ Süni İntellektə qoşulma uğursuzdur.")

# Əsas ekran
col1, col2 = st.columns([2, 1])

with col1:
    movzu = st.text_area(
        "Yazılacaq press-relizin mövzusu və əsas detalları (Məsələn: DOST mərkəzində yeni layihə, iştirakçılar, hədəflər...):",
        height=200)

with col2:
    st.markdown("#### 🔗 Mənbə məlumatı")
    st.markdown("Mənbə kimi **sosial.gov.az/az/media/xeberler** səhifəsinin son xəbərləri istifadə edilir.")

# ====================================================================
# 4. GENERASİYA (MƏTNİN YARADILMASI)
# ====================================================================
if st.button("🚀 Press-Relizi Yarat", use_container_width=True):
    if not model:
        st.error("Sistem Süni İntellektə qoşula bilməyib. Zəhmət olmasa Streamlit Cloud ayarlarını yoxlayın.")
    elif not movzu:
        st.warning("Zəhmət olmasa, press-relizin mövzusunu daxil edin!")
    else:
        with st.spinner("Sosial.gov.az saytındakı son xəbərlər analiz edilir və yeni mətn yazılır..."):
            try:
                uslub_metni = fetch_news_context()

                prompt = f"""
                Sən Azərbaycan Respublikası Əmək və Əhalinin Sosial Müdafiəsi Nazirliyinin peşəkar PR mütəxəssisisən. 
                Aşağıdakı mətn nazirliyin rəsmi saytından götürülmüş əvvəlki xəbərlərdir. Bu mətnin rəsmi, aydın və bürokratik üslubunu diqqətlə öyrən:

                {uslub_metni}

                İndi isə yuxarıdakı rəsmi üsluba və tonallığa tam uyğun olaraq, aşağıdakı mövzu əsasında yeni, unikal və mediaya göndərilmək üçün hazır olan bir press-reliz yaz. Mətni rəsmi başlıqla başlat və peşəkar abzaslara böl.

                Mövzu və detallar: {movzu}
                """

                response = model.generate_content(prompt)

                st.success("Press-reliz uğurla yaradıldı!")
                st.markdown("### 📄 Hazır Press-Reliz:")
                st.write(response.text)

            except Exception as e:
                st.error(f"Xəta baş verdi. Detallar: {e}")
