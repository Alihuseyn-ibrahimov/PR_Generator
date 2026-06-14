import streamlit as st
import google.generativeai as genai
import urllib.parse
import re
import requests
import base64
from bs4 import BeautifulSoup

# ====================================================================
# 1. AI MODELİNİN AYARLANMASI
# ====================================================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error("API açarı tapılmadı! Lütfən .streamlit/secrets.toml faylını yoxlayın.")

# ====================================================================
# 2. VİZUAL DİZAYN (UNIVERSAL RƏSMİ ÜSLUB)
# ====================================================================
st.set_page_config(
    page_title="Universal Press-Reliz Sistemi",
    page_icon="🇦🇿",
    layout="wide"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap');

:root {
  --esas-fon: #F8FAFC;        
  --qutu-fon: #FFFFFF;        
  --metn-tund: #0F172A;       
  --metn-aciq: #475569;       
  --esas-mavi: #0D3B66;       
  --mavi-hover: #164E87;      
  --qizili-vurqu: #C5A059;    
  --haşiyə: #E2E8F0;          
}

.top-flag-bar {
    position: fixed; top: 0; left: 0; width: 100%; height: 6px;
    background: linear-gradient(90deg, #00B5E2 33.33%, #EF3340 33.33%, #EF3340 66.66%, #509E2F 66.66%);
    z-index: 999999;
}

.stApp { background-color: var(--esas-fon); font-family: 'Inter', sans-serif; }

.hero-block {
  background: var(--qutu-fon); border-radius: 8px; padding: 3rem 2rem;
  text-align: center; border: 1px solid var(--haşiyə);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-top: 1rem; margin-bottom: 2rem;
  position: relative; overflow: hidden;
}

.hero-block::before {
    content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 4px; background-color: var(--qizili-vurqu);
}

.hero-logo { width: 80px; margin-bottom: 1rem; }

.hero-title { font-family: 'Montserrat', sans-serif; font-size: 2rem; color: var(--esas-mavi); letter-spacing: -0.5px; font-weight: 800; }
.hero-subtitle { color: var(--metn-aciq); font-size: 1.05rem; margin-top: 0.5rem; font-weight: 500; font-family: 'Inter', sans-serif; }

.section-title { font-family: 'Montserrat', sans-serif; font-size: 1.15rem; color: var(--esas-mavi); font-weight: 700; border-bottom: 2px solid var(--haşiyə); padding-bottom: 0.5rem; margin-top: 1.5rem; margin-bottom: 1rem; }

div[data-testid="stForm"] { background: var(--qutu-fon) !important; border: 1px solid var(--haşiyə) !important; padding: 2rem !important; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important; }

.source-box { background: #F1F5F9; border: 1px solid var(--haşiyə); border-left: 4px solid var(--qizili-vurqu); border-radius: 4px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
.source-box a { color: var(--esas-mavi); font-weight: 600; text-decoration: none; font-family: 'Montserrat', sans-serif; }
.source-box a:hover { text-decoration: underline; color: var(--mavi-hover); }

div[data-testid="stFormSubmitButton"] button { background-color: var(--esas-mavi) !important; color: #ffffff !important; border: none !important; border-radius: 4px !important; font-weight: 600 !important; font-family: 'Montserrat', sans-serif; letter-spacing: 0.5px; transition: all 0.3s ease; padding: 0.6rem 1.2rem !important; width: 100%; }
div[data-testid="stFormSubmitButton"] button:hover { background-color: var(--mavi-hover) !important; box-shadow: 0 4px 12px rgba(13, 59, 102, 0.2) !important; }

.result-box { background: var(--qutu-fon); padding: 2rem; border-radius: 8px; border-left: 4px solid var(--esas-mavi); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); font-family: 'Inter', serif; font-size: 1.05rem; line-height: 1.7; color: var(--metn-tund); }
</style>

<div class="top-flag-bar"></div>
""", unsafe_allow_html=True)


# ====================================================================
# 3. KÖMƏKÇİ FUNKSİYALAR (LOQO VƏ MƏTN)
# ====================================================================
def herfleri_temizle(metn):
    if not metn: return ""
    deyismeler = {'ə': 'e', 'Ə': 'E', 'ı': 'i', 'İ': 'I', 'ö': 'o', 'Ö': 'O', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S', 'ç': 'c', 'Ç': 'C'}
    for az, en in deyismeler.items(): metn = metn.replace(az, en)
    return re.sub(r'[^a-zA-Z0-9\s]', '', metn).strip()

@st.cache_data(ttl=86400, show_spinner=False)
def get_image_base64(url):
    """Şəkli arxa planda yükləyib Base64 koduna çevirir (Qırılan şəkillərin qarşısını alır)"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'image/png')
            encoded = base64.b64encode(response.content).decode()
            return f"data:{content_type};base64,{encoded}"
    except:
        pass
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_company_logo_base64(url):
    """Saytın linkinə əsasən qurumun rəsmi loqosunu tapır və Base64 olaraq qaytarır"""
    try:
        domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
        if not domain: return None
        
        # 1. Clearbit API (Daha yüksək keyfiyyətli loqolar üçün)
        clearbit_url = f"https://logo.clearbit.com/{domain}"
        b64 = get_image_base64(clearbit_url)
        if b64: return b64
        
        # 2. Google Favicon (Əgər loqo tapılmazsa, kiçik ikon qaytarır)
        google_url = f"https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{domain}&size=128"
        return get_image_base64(google_url)
    except:
        return None

def get_image_url(news_topic_eng):
    tehlukesiz_ad = herfleri_temizle(news_topic_eng) or "official government meeting"
    default_image = "https://images.unsplash.com/photo-1577962917302-cd874c4e31d2?auto=format&fit=crop&w=1024&q=80"
    try:
        url = f"https://api.unsplash.com/search/photos?page=1&query={urllib.parse.quote(tehlukesiz_ad + ' government')}&client_id={st.secrets['UNSPLASH_API_KEY']}&per_page=1&orientation=landscape"
        response = requests.get(url, timeout=3).json()
        if response.get('results'): return response['results'][0]['urls']['regular']
    except Exception: pass
    return default_image


# ====================================================================
# 3.1 UNİVERSAL XƏBƏR SKREYPINQİ
# ====================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dynamic_news_list(base_url):
    news_items = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(base_url, headers=headers, timeout=10)
        if resp.status_code != 200: return news_items
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        parsed_uri = urllib.parse.urlparse(base_url)
        domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
        
        for a_tag in soup.find_all('a', href=True):
            title = re.sub(r'\s+', ' ', a_tag.get_text(strip=True))
            href = a_tag['href']
            
            if 25 < len(title) < 200:
                if href.startswith('/'): href = domain + href
                if domain in href and href not in [item["link"] for item in news_items]:
                    news_items.append({"title": title, "link": href})
    except Exception:
        pass
    return news_items

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_article_text(article_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(article_url, headers=headers, timeout=8)
        if resp.status_code != 200: return ""
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        for script in soup(["script", "style", "header", "footer", "nav", "aside"]):
            script.extract()
            
        paragraphs = soup.find_all('p')
        clean_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        return "\n".join(clean_paragraphs)[:4000]
    except:
        return ""

STOP_WORDS = {"ucun", "olan", "olub", "edib", "edilib", "barede", "haqqinda", "ile", "bagli", "vetendaslari", "qebul", "tedbir", "tedbirler", "kecirilib", "teskil", "olunub", "melumat", "verilib", "daha", "cox", "min", "milyon", "milyard", "manat", "aylarinda", "ayinda", "ilinde", "respublikasi", "azerbaycan", "nazirliyin", "nazirliyi", "sahesinde", "movzusunda", "uzre", "yeni", "bu", "bir", "ve", "ya", "ki", "de", "da", "ile", "olaraq", "etrafinda", "haqda"}

def acar_sozler(metn):
    return {w for w in herfleri_temizle(metn).lower().split() if len(w) > 3 and w not in STOP_WORDS}

def find_similar_news(movzu, sirket_adi, news_items, top_n=2, min_score=2):
    if not news_items: return []
    movzu_sozler = acar_sozler(movzu) | acar_sozler(sirket_adi)
    if not movzu_sozler: return []
    scored = []
    for item in news_items:
        ortaq = movzu_sozler & acar_sozler(item["title"])
        if len(ortaq) >= min_score: scored.append((len(ortaq), item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_n]]


# Session State
if "pr_response" not in st.session_state: st.session_state.pr_response = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "found_news" not in st.session_state: st.session_state.found_news = []
if "source_domain_url" not in st.session_state: st.session_state.source_domain_url = None

# ====================================================================
# HERO BÖLMƏSİ (Base64 Gerb Həlli)
# ====================================================================
# Gerbi etibarlı mənbədən arxa planda çəkirik
gerb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Emblem_of_Azerbaijan.svg/500px-Emblem_of_Azerbaijan.svg.png"
gerb_base64 = get_image_base64(gerb_url)
# Əgər wikipedia nəsə problem yaradarsa, ehtiyat olaraq Azərbaycan bayrağı görünsün
hero_logo_src = gerb_base64 if gerb_base64 else "https://flagcdn.com/w160/az.png"

st.markdown(
    f'''
    <div class="hero-block">
        <img src="{hero_logo_src}" alt="Gerb" class="hero-logo">
        <div class="hero-title">Universal Press-Reliz Sistemi</div>
        <div class="hero-subtitle">İstənilən qurumun veb-saytını daxil edərək həmin qurumun korporativ üslubuna uyğun rəsmi xəbərlər yaradın.</div>
    </div>
    ''',
    unsafe_allow_html=True)

# ====================================================================
# 4. FORM (PR PARAMETRLƏRİ)
# ====================================================================
with st.form("pr_form"):
    st.markdown('<div class="section-title">🏢 Məlumatların Daxil Edilməsi</div>', unsafe_allow_html=True)

    sirket_adi = st.text_input("Qurum, Şirkət və ya Layihənin Adı", placeholder="Məs: İqtisadiyyat Nazirliyi, ASAN Xidmət, PASHA Bank...")

    movzu = st.text_area("Tədbirin və ya Xəbərin Məzmunu",
                         placeholder="Əsas faktları qeyd edin (məsələn: Vətəndaşlara xidmət edəcək yeni portalın təqdimatı keçirildi...)",
                         height=100)
    
    st.markdown('<div class="section-title">📡 Mənbə və Üslub Təyini</div>', unsafe_allow_html=True)
    
    menbe_url = st.text_input("Öyrəniləcək Veb-sayt (Xəbərlər bölməsinin linkini daxil edin)", 
                              value="https://sosial.gov.az/az/media/xeberler",
                              help="Süni intellekt bu linkə daxil olub qurumunuzun yazı üslubunu və cümlə quruluşunu analiz edəcək.")

    st.markdown('<div class="section-title">🎯 Tənzimləmələr</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        hedef_kutle = st.selectbox("Hədəf Kütlə", ["Geniş İctimaiyyət", "Rəsmi Nümayəndələr", "İxtisaslaşmış Media", "Vətəndaşlar"])
    with col2:
        ses_tonu = st.selectbox("Səs Tonu", ["Rəsmi / Dövlət üslubu", "İnformasiya xarakterli", "Analitik", "Kreativ / Korporativ"])
    with col3:
        dil = st.selectbox("Dil", ["Azərbaycanca", "English", "Русский"])

    sosial_istifade = st.checkbox(
        "Mətni yuxarıda daxil etdiyim saytın korporativ xəbər standartlarına uyğunlaşdır",
        value=True
    )

    submitted = st.form_submit_button("Sənədi Formalaşdır")

# ====================================================================
# 5. AI GENERASİYA
# ====================================================================
if submitted:
    if not movzu.strip() or not sirket_adi.strip() or not menbe_url.strip():
        st.warning("⚠️ Zəhmət olmasa, Qurum adını, Veb-sayt linkini və Xəbərin məzmununu tam daxil edin!")
    else:
        st.session_state.chat_history = []
        st.session_state.found_news = []
        st.session_state.source_domain_url = menbe_url 
        reference_block = ""

        if sosial_istifade:
            with st.spinner(f"🔎 {urllib.parse.urlparse(menbe_url).netloc} saytı analiz edilir və uyğun xəbərlər axtarılır..."):
                news_list = fetch_dynamic_news_list(menbe_url)
                similar_news = find_similar_news(movzu, sirket_adi, news_list, top_n=2, min_score=1)

                if not similar_news and news_list:
                    similar_news = news_list[:2]

                reference_texts = []
                for item in similar_news:
                    article_text = fetch_article_text(item["link"])
                    if article_text:
                        reference_texts.append(f"Başlıq: {item['title']}\nMətn: {article_text}")
                        st.session_state.found_news.append(item)

                if reference_texts:
                    reference_block = "\n\n---\n\n".join(reference_texts)
                else:
                    st.info("ℹ️ Qeyd edilən saytda oxşar standartlı xəbər tapılmadı. Mətn yalnız sizin verdiyiniz məlumatlara əsasən yazılacaq.")

        with st.spinner("⏳ Süni İntellekt rəsmi məlumatı hazırlayır..."):
            if reference_block:
                reference_instruction = f"""
            REFERANS XƏBƏRLƏR (Qurumun rəsmi veb-sayt standartları):
            Aşağıdakı xəbərlərin DİL ÜSLUBUNA, TONUNA və ABZAS STRUKTURUNA diqqət yetir. 
            Hazırlayacağın press-reliz məhz bu qurumun ciddiyyətinə və PR formatına tam uyğun olmalıdır.
            Konkret rəqəmləri və faktları kopyalama, yalnız ŞABLON və ÜSLUB kimi istifadə et.

            --- REFERANS MƏTNLƏR BAŞLANIR ---
            {reference_block}
            --- REFERANS MƏTNLƏR SONA ÇATIR ---
            """
            else:
                reference_instruction = ""

            prompt = f"""
            Sən {sirket_adi} üçün çalışan peşəkar Mətbuat Katibi və PR Menecerisən.
            İstifadəçinin verdiyi faktlar əsasında yüksək səviyyəli press-reliz hazırlamalısan.

            Məlumatlar:
            Qurum: {sirket_adi}
            Mövzu: {movzu}
            Hədəf Kütlə: {hedef_kutle}
            Səs Tonu: {ses_tonu}
            Dil: {dil}

            {reference_instruction}

            Tələblər:
            1. Bütün cavabı mütləq {dil} dilində, müvafiq üslubda yaz.
            2. TITLE və s. kimi prefikslərdən və ulduz işarələrindən istifadə etmə.
            3. PR Mətninin strukturu:
               - Başlıq
               - Lid Abzası (Faktların xülasəsi)
               - Əsas hissə (Təfərrüatlar, əhəmiyyəti, gələcək planlar)
            4. Mətn tamamilə unikal və orijinal olmalıdır.
            """

            try:
                response = model.generate_content(prompt)
                full_text = response.text.replace("**", "") 
                st.session_state.pr_response = full_text
            except Exception as e:
                st.error(f"Sistem xətası baş verdi: {e}")

# ====================================================================
# 6. NƏTİCƏNİN GÖSTƏRİLMƏSİ
# ====================================================================
if st.session_state.pr_response:
    st.markdown("---")

    # MƏNBƏ QURUMUN LOQOSUNUN GÖSTƏRİLMƏSİ (Base64 Həlli)
    if st.session_state.source_domain_url:
        logo_base64_src = get_company_logo_base64(st.session_state.source_domain_url)
        if logo_base64_src:
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 25px;">
                    <img src="{logo_base64_src}" alt="Şirkət Loqosu" style="width: 100px; height: 100px; object-fit: contain; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.06); padding: 10px; background: white;">
                </div>
            """, unsafe_allow_html=True)

    if st.session_state.found_news:
        domain_name = urllib.parse.urlparse(st.session_state.found_news[0]['link']).netloc
        st.markdown(f'<div class="section-title">🔗 Üslubu Öyrənilən Mənbələr ({domain_name})</div>', unsafe_allow_html=True)
        for item in st.session_state.found_news:
            st.markdown(f'<div class="source-box">📄 <a href="{item["link"]}" target="_blank">{item["title"]}</a></div>',
                        unsafe_allow_html=True)

    st.markdown('<div class="result-box">', unsafe_allow_html=True)
    st.markdown(st.session_state.pr_response)
    st.markdown('</div>', unsafe_allow_html=True)

    st.download_button("📥 Sənədi Yadda Saxla (.txt)", st.session_state.pr_response, "press_reliz.txt")

    # ====================================================================
    # 7. CHATBOT BÖLMƏSİ
    # ====================================================================
    st.markdown("---")
    st.markdown('<div class="section-title">💬 Mətbuat Katibi ilə Əlaqə</div>', unsafe_allow_html=True)
    st.info("Mətndəki hər hansı cümləni qısaltmaq, əlavələr etmək və ya daha fərqli formaya salmaq istəyirsinizsə, aşağıdan qeyd edə bilərsiniz.")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt_sual := st.chat_input("Tələbinizi bura yazın..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt_sual})
        with st.chat_message("user"):
            st.markdown(prompt_sual)

        with st.chat_message("assistant"):
            with st.spinner("Sorğu emal edilir..."):
                chat_context = f"Sən qurumun PR rəhbərisən. Mətn: {st.session_state.pr_response}\n\nİstifadəçi tələbi: {prompt_sual}\n\nYalnız bu tələbə uyğun rəsmi və qısa cavab ver."
                try:
                    chat_response = model.generate_content(chat_context)
                    st.markdown(chat_response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": chat_response.text})
                except Exception as e:
                    st.error(f"Sistem xətası: {e}")

# Footer
st.markdown(
    '<div style="text-align: center; margin-top: 3rem; color: #475569; font-size: 0.85rem;">Universal Məlumatlandırma Sistemi | Süni İntellekt Dəstəkli</div>',
    unsafe_allow_html=True)
