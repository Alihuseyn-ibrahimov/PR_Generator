import os

# ====================================================================
# --- AVTOMATİK LİMİT ARTIRICI SİSTEM (YENİ) ---
# Proqram işə düşməzdən əvvəl 2GB (2000MB) limiti avtomatik təyin edir
# ====================================================================
if not os.path.exists(".streamlit"):
    os.makedirs(".streamlit")

with open(".streamlit/config.toml", "w", encoding="utf-8") as f:
    f.write("[server]\nmaxUploadSize = 2000\n")

import streamlit as st
import google.generativeai as genai
import urllib.parse
import re
import requests
import base64
from bs4 import BeautifulSoup
from PIL import Image
import tempfile
import time
import datetime
from email.utils import parsedate_to_datetime

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


# ====================================================================
# 3. KÖMƏKÇİ FUNKSİYALAR
# ====================================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_image_base64(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'image/png')
            encoded = base64.b64encode(response.content).decode()
            return f"data:{content_type};base64,{encoded}"
    except:
        pass
    return None


def az_lower(text):
    if not text: return ""
    deyismeler = {'İ': 'i', 'I': 'ı', 'Ə': 'ə', 'Ö': 'ö', 'Ü': 'ü', 'Ş': 'ş', 'Ç': 'ç', 'Ğ': 'ğ'}
    for boyuk, kicik in deyismeler.items():
        text = text.replace(boyuk, kicik)
    return text.lower()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_article_text(article_url):
    """Mənbə linkindən mətni (abzasları) çəkən funksiya (Üslub analizi üçün)"""
    if not article_url:
        return ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(article_url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs if len(p.get_text()) > 20])
        return text[:3000]  # Token limitini aşmamaq üçün
    except Exception as e:
        return ""


# --- AXTARIŞ MOTORLARI VƏ FİLTRLƏR ---
def search_latest_news(keyword, start_date, end_date):
    results = []
    seen_links = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "az-AZ,az;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    def strict_keyword_filter(text, kw):
        if not text: return False
        text_lower = az_lower(text)
        kw_lower = az_lower(kw)
        if kw_lower in text_lower: return True
        words = [w for w in kw_lower.split() if len(w) > 3]
        if not words: return kw_lower in text_lower
        match_count = sum(1 for w in words if w[:5] in text_lower)
        return match_count >= len(words) * 0.7

    def relaxed_keyword_filter(text, kw):
        if not text: return False
        text_lower = az_lower(text)
        kw_lower = az_lower(kw)
        if kw_lower in text_lower: return True
        words = [w[:5] for w in kw_lower.split() if len(w) > 3]
        match_count = sum(1 for w in words if w in text_lower)
        return match_count >= 1

    def strict_date_filter(pubdate_text):
        if not pubdate_text: return True
        try:
            dt = parsedate_to_datetime(pubdate_text).date()
            return start_date <= dt <= end_date
        except Exception:
            return True

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_search_str = (end_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # MOTOR 1: GOOGLE NEWS
    gn_query = f'{keyword} site:.az after:{start_date_str} before:{end_date_search_str}'
    gn_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(gn_query)}&hl=az&gl=AZ&ceid=AZ:az"
    try:
        resp = requests.get(gn_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'xml')
        for item in soup.find_all('item'):
            title = item.title.text if item.title else ""
            link = item.link.text if item.link else ""
            desc = item.description.text if item.description else ""
            pub_date = item.pubDate.text if item.pubDate else ""

            if strict_keyword_filter(title + " " + desc, keyword) and strict_date_filter(pub_date):
                if link not in seen_links:
                    seen_links.add(link)
                    results.append({"title": title, "link": link})
            if len(results) >= 10: break
    except Exception:
        pass

    # MOTOR 2: DUCKDUCKGO HTML
    if len(results) < 20:
        sm_query = f'"{keyword}" (site:facebook.com OR site:instagram.com OR site:t.me OR site:gov.az)'
        try:
            ddg_url = "https://html.duckduckgo.com/html/"
            ddg_headers = headers.copy()
            ddg_headers["Content-Type"] = "application/x-www-form-urlencoded"

            resp = requests.post(ddg_url, data={"q": sm_query}, headers=ddg_headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for result in soup.find_all('div', class_='result'):
                    a_tag = result.find('a', class_='result__url')
                    title_tag = result.find('h2', class_='result__title')
                    snippet_tag = result.find('a', class_='result__snippet')

                    if a_tag and title_tag:
                        raw_link = a_tag.get('href', '')
                        if '//duckduckgo.com/l/?uddg=' in raw_link:
                            try:
                                link = urllib.parse.unquote(raw_link.split('uddg=')[1].split('&')[0])
                            except:
                                link = raw_link
                        else:
                            link = raw_link

                        title = title_tag.text.strip()
                        snippet = snippet_tag.text.strip() if snippet_tag else ""

                        if relaxed_keyword_filter(title + " " + snippet, keyword):
                            if link not in seen_links:
                                seen_links.add(link)
                                results.append({"title": f"[Rəsmi/Sosial] {title}", "link": link})
                        if len(results) >= 15: break
        except Exception:
            pass

    # MOTOR 3: YAHOO SEARCH
    if len(results) < 15:
        try:
            y_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(sm_query)}"
            y_resp = requests.get(y_url, headers=headers, timeout=10)
            if y_resp.status_code == 200:
                y_soup = BeautifulSoup(y_resp.text, 'html.parser')
                for div in y_soup.find_all('div', class_='compTitle'):
                    a_tag = div.find('a')
                    if a_tag:
                        raw_link = a_tag.get('href', '')
                        title = a_tag.text.strip()
                        link = raw_link
                        if 'RU=' in raw_link:
                            try:
                                link = urllib.parse.unquote(raw_link.split('RU=')[1].split('/')[0])
                            except:
                                pass

                        if relaxed_keyword_filter(title, keyword):
                            if link not in seen_links:
                                seen_links.add(link)
                                results.append({"title": f"[Rəsmi/Sosial] {title}", "link": link})
                        if len(results) >= 20: break
        except Exception:
            pass

    return results


# Session State
if "pr_response" not in st.session_state: st.session_state.pr_response = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "source_domain_url" not in st.session_state: st.session_state.source_domain_url = None

# ====================================================================
# HERO BÖLMƏSİ
# ====================================================================
gerb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Emblem_of_Azerbaijan.svg/500px-Emblem_of_Azerbaijan.svg.png"
gerb_base64 = get_image_base64(gerb_url)
hero_logo_src = gerb_base64 if gerb_base64 else "https://flagcdn.com/w160/az.png"

st.markdown(
    f'''
    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 10px; margin-bottom: 20px;">
        <img src="{hero_logo_src}" width="80" style="margin-bottom: 15px;">
        <h1 style="color: #1f2937; font-size: 28px; margin-bottom: 10px;">Universal PR və Monitorinq Sistemi</h1>
        <p style="color: #4b5563; font-size: 16px;">Süni İntellekt dəstəkli 3-ü 1-də PR İdarəetmə Platforması</p>
    </div>
    ''',
    unsafe_allow_html=True
)

# ====================================================================
# YAN MENYU (SİDEBAR) - REJİM SEÇİMİ
# ====================================================================
st.sidebar.markdown("## 🛠️ İş Rejimi")
rejim = st.sidebar.radio(
    "Zəhmət olmasa bölməni seçin:",
    ["📝 Press-Reliz Yarat", "📱 Sosial Media Postu Yarat", "📊 Media Monitorinqi"]
)

# ====================================================================
# REJİM 1: PRESS-RELİZ YARAT
# ====================================================================
if rejim == "📝 Press-Reliz Yarat":
    with st.form("pr_form"):
        st.markdown('### 🏢 Məlumatların Daxil Edilməsi')
        sirket_adi = st.text_input("Qurum, Şirkət və ya Layihənin Adı", placeholder="Məs: İqtisadiyyat Nazirliyi...")
        movzu = st.text_area("Tədbirin və ya Xəbərin Məzmunu", height=100)

        menbe_url = st.text_input("İstinad və Üslub üçün Mənbə Linki (Köhnə xəbər linki)",
                                  placeholder="Məs: https://sosial.gov.az/az/xaberler/...")

        st.markdown('### 🎯 Tənzimləmələr')
        col1, col2, col3 = st.columns(3)
        with col1: hedef_kutle = st.selectbox("Hədəf Kütlə",
                                              ["Geniş İctimaiyyət", "Rəsmi Nümayəndələr", "İxtisaslaşmış Media",
                                               "Vətəndaşlar"])
        with col2: ses_tonu = st.selectbox("Səs Tonu", ["Rəsmi / Dövlət üslubu", "İnformasiya xarakterli", "Analitik",
                                                        "Kreativ / Korporativ"])
        with col3: dil = st.selectbox("Dil", ["Azərbaycanca", "English", "Русский"])

        submitted = st.form_submit_button("Sənədi Formalaşdır")

    if submitted:
        if not movzu.strip() or not sirket_adi.strip():
            st.warning("⚠️ Zəhmət olmasa lazımi xanaları doldurun (Qurum adı və Məzmun məcburidir)!")
        else:
            st.session_state.source_domain_url = menbe_url
            with st.spinner("⏳ Süni İntellekt rəsmi məlumatı hazırlayır və mənbəni analiz edir..."):

                uslub_metni = fetch_article_text(menbe_url) if menbe_url else ""

                prompt = f"""
                Sən {sirket_adi} üçün çalışan peşəkar Mətbuat Katibi və PR Menecerisən.
                Mövzu: {movzu}
                Hədəf Kütlə: {hedef_kutle}
                Səs Tonu: {ses_tonu}
                Dil: {dil}

                {"DİQQƏT: Press-relizin üslubu, tonu və cümlə quruluşu aşağıda təqdim edilən, qurumun əvvəlki xəbərlərinin üslubu ilə eyni olmalıdır! ÜSLUB NÜMUNƏSİ: " + uslub_metni if uslub_metni else "Üslub nümunəsi verilməyib, standart rəsmi dövlət/korporativ üslubdan istifadə et."}

                Bütün cavabı mütləq {dil} dilində yaz. Çox rəsmi və dolğun olsun.
                """
                try:
                    response = model.generate_content(prompt)
                    st.session_state.pr_response = response.text
                    st.success("Sənəd uğurla formalaşdırıldı!")
                except Exception as e:
                    st.error(f"Sistem xətası: {e}")

    if st.session_state.pr_response:
        st.markdown("---")

        if st.session_state.source_domain_url:
            st.info(
                f"🔗 **Üslub üçün analiz edilən mənbə linki:** [{st.session_state.source_domain_url}]({st.session_state.source_domain_url})")

        st.markdown(st.session_state.pr_response)
        st.download_button("📥 Sənədi Yadda Saxla (.txt)", st.session_state.pr_response, "press_reliz.txt")

# ====================================================================
# REJİM 2: SOSİAL MEDİA POSTU YARAT
# ====================================================================
elif rejim == "📱 Sosial Media Postu Yarat":
    st.markdown('### 📱 Sosial Şəbəkə Paylaşımı (Post) Yarat')
    st.info(
        "Mətn yapışdıraraq və ya yalnız Poster/Video yükləyərək avtomatik sosial şəbəkə başlıqları (caption) əldə edə bilərsiniz.")

    sm_text = st.text_area("Xəbərin Mətni (Varsa)",
                           value=st.session_state.pr_response if st.session_state.pr_response else "", height=150)
    sm_link = st.text_input("Oxşadılacaq Mənbə Linki", value="https://www.facebook.com/share/18jAVekQrN/")

    # Yeni limitsiz fayl yükləyicisi
    uploaded_file = st.file_uploader("Şəkil və ya Video yüklə (2GB-a qədər)", type=['jpg', 'jpeg', 'png', 'mp4'])

    if st.button("Post Başlığını Hazırla"):
        with st.spinner("Süni İntellekt sosial media postunu hazırlayır..."):
            prompt = f"Aşağıdakı məlumata əsasən sosial şəbəkə (xüsusən {sm_link} tərzində) postu yaz:\n\n{sm_text}"
            if not sm_text and uploaded_file:
                prompt = "Verilmiş faylı analiz et və birbaşa onun məzmununa uyğun rəsmi PR postu/başlığı (caption) hazırla."

            try:
                if uploaded_file is not None:
                    if uploaded_file.type in ['image/jpeg', 'image/png', 'image/jpg']:
                        image = Image.open(uploaded_file)
                        response = model.generate_content([prompt, image])
                    elif uploaded_file.type == 'video/mp4':
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_vid:
                            tmp_vid.write(uploaded_file.read())
                            tmp_vid_path = tmp_vid.name
                        video_file = genai.upload_file(path=tmp_vid_path)
                        while video_file.state.name == "PROCESSING":
                            time.sleep(2)
                            video_file = genai.get_file(video_file.name)
                        response = model.generate_content([prompt, video_file])
                        os.unlink(tmp_vid_path)
                else:
                    response = model.generate_content(prompt)

                st.markdown("---")
                st.markdown("### 📝 Sizin üçün hazırlanan Post:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Xəta baş verdi. (Əgər Limit xətasıdırsa, 1 dəqiqə gözləyib yenidən cəhd edin). Detal: {e}")

# ====================================================================
# REJİM 3: MEDIA MONITORINQİ VƏ SENTİMENT ANALİZİ (YENİ SİSTEM)
# ====================================================================
elif rejim == "📊 Media Monitorinqi":
    st.markdown('### 📊 Vahid Media Monitorinqi və Sentiment Analizi')

    st.markdown("#### 🗓️ Axtarış Aralığını Seçin")
    col1, col2 = st.columns(2)
    with col1:
        default_start = datetime.date.today() - datetime.timedelta(days=7)
        default_end = datetime.date.today()

        secilen_tarix = st.date_input(
            "Tarix Aralığı (Başlanğıc - Bitiş):",
            value=(default_start, default_end),
            max_value=datetime.date.today()
        )

    if len(secilen_tarix) == 2:
        start_date = secilen_tarix[0]
        end_date = secilen_tarix[1]
    else:
        start_date = secilen_tarix[0]
        end_date = secilen_tarix[0]

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    st.info(
        "İzləniləcək açar sözləri hər sətrə bir dənə olmaqla daxil edin. Hesabat tam olaraq sizin daxil etdiyiniz bu ardıcıllıqla qurulacaq.")

    default_keywords = """Əmək və Əhalinin Sosial Müdafiəsi Nazirliyi
Dövlət Sosial Müdafiə Fondu
Dövlət Əmək Müffətişliyi Xidməti
Sosial Xidmətlər Agentliyi
DOST Agentliyi
Anar Əliyev
Ünvanlı sosial yardım
Əlillik
İşsizlik
Dövlət Tibbi Sosial Ekpertiza və Reabilitasiya Agentliyi
Minimum əmək haqqı"""

    acar_sozler_input = st.text_area(
        "İzləniləcək Açar Sözlər:",
        value=default_keywords,
        height=250
    )

    if st.button(f"Monitorinqə Başla ({start_date_str} - {end_date_str})"):
        keywords = [k.strip() for k in acar_sozler_input.split('\n') if k.strip()]

        if not keywords:
            st.warning("Zəhmət olmasa ən azı bir açar söz daxil edin.")
        else:
            with st.spinner(
                    f"Sistem məlumatları toplayır və vahid hesabat formalaşdırır... Bu bir qədər vaxt apara bilər."):

                all_news_text = ""
                found_any_news = False

                for kw in keywords:
                    xəbərlər = search_latest_news(kw, start_date, end_date)
                    all_news_text += f"\n\n[AÇAR SÖZ: {kw}]\n"

                    if not xəbərlər:
                        all_news_text += "Məlumat tapılmadı.\n"
                    else:
                        found_any_news = True
                        for item in xəbərlər:
                            all_news_text += f"- Başlıq: {item['title']}\n  Link: {item['link']}\n"

                if not found_any_news:
                    st.warning("Seçilmiş tarixlər aralığında heç bir açar söz üzrə məlumat tapılmadı.")
                else:
                    sentiment_prompt = f"""
                    Sən peşəkar PR və Media Analitikisən. Aşağıdakı məlumatlar {start_date_str} və {end_date_str} tarixləri aralığında verilmiş açar sözlər üzrə toplanmış xəbərlərdir.

                    DÖVLƏT ORQANI ÜÇÜN QƏTİ QAYDALAR:
                    1. YALNIZ və YALNIZ "Xəbərlər bazası"nda sənə verilən məlumatlardan və linklərdən istifadə et! 
                    2. Özündən qətiyyən heç bir xəbər, link və ya məlumat uydurma (hallüsinasiya etmə)! Əgər məlumat yoxdursa, uydurmaq əvəzinə "Bu kateqoriyada qeydə alınmış xəbər tapılmadı" yaz.
                    3. Başqa ölkəyə (Türkmənistan, Türkiyə, Rusiya və s.) aid xəbərləri dərhal sil və hesabatda göstərmə!
                    4. Bütün hesabatı yalnız mükəmməl AZƏRBAYCAN DİLİNDƏ yaz.

                    ƏN VACİB VƏZİFƏN HESABATIN STRUKTURUNU QURMAQDIR:
                    Sən hesabatı açar sözlərə görə deyil, 3 ƏSAS SENTİMENT KATEQORİYASINA görə bölməlisən. 
                    Format bu cür olmalıdır:

                    ## 🟢 MÜSBƏT XƏBƏRLƏR
                    (Burada yalnız müsbət xarakterli xəbərləri yaz. Xəbərləri alt-başlıq kimi mənim "Xəbərlər bazası"nda sənə verdiyim AÇAR SÖZLƏRİN ARDICILLIĞI İLƏ qruplaşdır. Məsələn:
                    **1. Əmək və Əhalinin Sosial Müdafiəsi Nazirliyi**
                    - Xəbər (Link)
                    **2. Dövlət Sosial Müdafiə Fondu**
                    - Xəbər (Link)
                    Və s.)

                    ## 🟡 NEYTRAL XƏBƏRLƏR
                    (Burada yalnız neytral, informativ xəbərləri eyni ardıcıllıqla qruplaşdır. Hər xəbərin sonuna orijinal linkini əlavə et.)

                    ## 🔴 MƏNFİ VƏ YA KRİZİS XƏBƏRLƏRİ
                    (Burada şikayət, tənqid və s. olan mənfi xəbərləri eyni ardıcıllıqla qruplaşdır. Hər xəbərin sonuna orijinal linkini əlavə et.)

                    Xəbərlər bazası (İzlənilməli olan ardıcıllıqla):
                    {all_news_text}
                    """

                    try:
                        ai_analiz = model.generate_content(sentiment_prompt)
                        st.markdown(f"# 📊 Vahid PR Monitorinq Hesabatı ({start_date_str} / {end_date_str})")
                        st.markdown("---")
                        st.markdown(ai_analiz.text)
                    except Exception as e:
                        st.error(f"Hesabat formalaşdırılarkən xəta baş verdi: {e}")

# Footer
st.markdown("<br><hr><center><p style='color: gray;'>Universal PR Sistemi | Süni İntellekt Dəstəkli 🤖</p></center>",
            unsafe_allow_html=True)
