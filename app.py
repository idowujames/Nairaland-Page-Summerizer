import os
import requests
import google.generativeai as genai
import streamlit as st
import cloudscraper
from curl_cffi import requests as cffi_requests
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
from google.api_core.exceptions import ResourceExhausted
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse

# --- Page Configuration ---
st.set_page_config(
    page_title="Nairaland Topic Summarizer",
    page_icon="🇳�",
    layout="wide"
)

# --- API Key Configuration ---
# Initialize session state for API key if it doesn't exist
if 'api_key_configured' not in st.session_state:
    st.session_state.api_key_configured = False

# Sidebar for API key input
with st.sidebar:
    st.header("API Configuration")
    
    # Input field for API key
    api_key = st.text_input(
        "Enter your Gemini API Key:",
        type="password",
        placeholder="Enter your API key here",
        help="Get your API key from https://aistudio.google.com/app/apikey"
    )
    
    # Button to save the API key
    if st.button("Save API Key"):
        if api_key:
            try:
                # Try to configure the API with the provided key
                genai.configure(api_key=api_key)
                st.session_state.api_key_configured = True
                st.session_state.api_key = api_key
                st.sidebar.success("API key saved successfully!")
            except Exception as e:
                st.sidebar.error(f"Error configuring API: {str(e)}")
        else:
            st.sidebar.warning("Please enter an API key")

# Check if API key is configured before proceeding
if not st.session_state.get('api_key_configured', False):
    st.warning("⚠️ Please enter and save your Gemini API key in the sidebar to continue.")
    st.stop()

# Configure the API with the saved key
genai.configure(api_key=st.session_state.api_key)

# CORE SCRAPING & SUMMARIZING FUNCTIONS
@st.cache_data(ttl=600) # Cache results for 10 minutes to avoid re-scraping
def get_page_urls_to_scrape(topic_url, num_pages_to_scrape):
    """Finds the URLs for the last 'n' pages of a Nairaland topic."""
    st.info(f"Finding the last {num_pages_to_scrape} page(s) for topic...")
    try:
        # Use curl_cffi to bypass Cloudflare with authentic TLS fingerprint
        # impersonate="chrome110" mimics a real Chrome browser
        response = cffi_requests.get(get_clean_topic_url(topic_url), impersonate="chrome110", timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        reply_link = soup.find('a', href=lambda href: href and 'newpost?topic=' in href)

        if not reply_link: 
            return [get_clean_topic_url(topic_url)]

        pagination_p = reply_link.find_parent('p')

        if not pagination_p: 
            return [get_clean_topic_url(topic_url)]

        page_tags = pagination_p.find_all(['a', 'b'])
        
        last_page_num = 0
        for tag in page_tags:
            tag_text = tag.get_text(strip=True)
            if tag_text.startswith('(') and tag_text.endswith(')'):
                try: num = int(tag_text.strip('()'))
                except ValueError: continue
            elif tag_text.isdigit():
                 try: num = int(tag_text)
                 except ValueError: continue
            else: continue
            
            if num > last_page_num: last_page_num = num

        last_page_num = max(1, last_page_num)
        start_page = max(1, last_page_num - num_pages_to_scrape + 1)
        urls_to_scrape = []
        base_url = get_clean_topic_url(topic_url)
        st.info(f"Total pages: {last_page_num}. Scraping from page {start_page} to {last_page_num}.")
        for page_num in range(start_page, last_page_num + 1):
            if page_num == 1: urls_to_scrape.append(base_url)
            else: urls_to_scrape.append(f"{base_url}/{page_num - 1}")
        return urls_to_scrape
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while finding the last page: {e}")
        return [get_clean_topic_url(topic_url)]

def get_clean_topic_url(url):
    """Helper function to strip page numbers from a URL."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) > 1:
        clean_path = '/' + '/'.join(path_parts[:2])
        return urlunparse((parsed.scheme, parsed.netloc, clean_path, '', '', ''))
    return url # Return original if path is not as expected

def parse_html_content(html_content, page_url):
    """Parses Nairaland HTML to extract posts."""
    soup = BeautifulSoup(html_content, 'lxml')
    posts_data = []
    posts_table = soup.find('table', summary='posts')
    if not posts_table: return []
    post_bodies = posts_table.find_all('td', class_='l w pd')
    for post_body in post_bodies:
        narrow_div = post_body.find('div', class_='narrow')
        if not narrow_div: continue
        quotes = [q.get_text(separator=' ', strip=True) for q in narrow_div.find_all('blockquote')]
        for q in narrow_div.find_all('blockquote'): q.decompose()
        post_text = narrow_div.get_text(separator=' ', strip=True)
        if not post_text: continue
        header_row = post_body.find_parent('tr').find_previous_sibling('tr')
        if not header_row: continue
        author_tag = header_row.find('a', class_='user')
        author = author_tag.get_text(strip=True) if author_tag else "Unknown"
        post_id_tag = header_row.find('a', attrs={'name': lambda x: x and x.startswith('msg')})
        post_link = f"{page_url}#{post_id_tag['name'].replace('msg', '')}" if post_id_tag else page_url
        posts_data.append({'author': author, 'post_text': post_text, 'quoted_posts': quotes, 'link': post_link})
    return posts_data

@st.cache_data(ttl=600)
def fetch_and_parse_url(url):
    """Fetches and parses a URL for Nairaland posts."""
    try:
        # Use curl_cffi to bypass Cloudflare with authentic TLS fingerprint
        response = cffi_requests.get(url, impersonate="chrome110", timeout=15)
        response.raise_for_status()
        return parse_html_content(response.text, url)
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not fetch {url}: {e}")
        return []

def format_posts_for_llm(posts):
    """Formats the list of post dictionaries into a single string for the LLM."""
    formatted_string = ""
    for post in posts:
        formatted_string += f"Post by: {post['author']}\n"
        if post['quoted_posts']:
            formatted_string += "".join([f"Quoting: \"{q}\"\n" for q in post['quoted_posts']])
        formatted_string += f"Comment: {post['post_text']}\n"
        formatted_string += f"Link: {post['link']}\n\n"
    return formatted_string

@st.cache_data(ttl=600)
@retry(
    retry=retry_if_exception_type(ResourceExhausted),
    wait=wait_random_exponential(multiplier=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True
)
def summarize_with_gemini(posts_text):
    """Sends the formatted post text to the Gemini API for summarization."""
    if not api_key:
        return "Cannot summarize because Gemini API key is not configured."

    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    prompt = f"""
    You are an expert at analyzing and summarizing online forum discussions.
    Based on the following collection of posts from a Nairaland topic, please provide:
    1.  **A Concise Summary:** A high-level overview of the main theme and what the current conversation is about. If multiple themes are being discussed, summarize each separately
    2.  **Key Discussion Points:** Identify the 2-4 main arguments, opinions, or themes being discussed by the users. 
    3.  **Relevant Posts:** A bulleted list of the most significant or representative posts that capture the essence of the discussion. For each post, you MUST include the author and the full link. Select posts that show different perspectives or contain valuable insights **Crucially, present the link as plain text and do not format it as a clickable Markdown link.**
    
    Note: Make the summary engaging and the aim should be to help the reader understand the topics well enough to decide if they want to engage with the full thread.

    Here is the discussion:\n---\n{posts_text}\n---
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_msg = f"An error occurred while communicating with the Gemini API: {e}"
        if "404" in str(e):
             try:
                 models = list(genai.list_models())
                 # Filter for generateContent supported models
                 supported_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
                 error_msg += f"\n\n**Available supported models:**\n" + "\n".join([f"- `{m}`" for m in supported_models])
             except Exception as list_e:
                 error_msg += f"\n\nCould not list available models: {list_e}"
        return error_msg

# --- STREAMLIT UI ---

st.title("Nairaland Topic Summarizer")
st.markdown("Enter a Nairaland topic URL to get an AI-powered summary of the latest conversations.")

# --- Input Form ---
with st.form("summarizer_form"):
    topic_url = st.text_input(
        "Nairaland Topic URL",
        "https://www.nairaland.com/390522/solar-energy-complement-fta"
    )
    pages_to_scrape_count = st.number_input(
        "How many of the LATEST pages do you want to scrape?",
        min_value=1, max_value=20, value=2, step=1
    )
    submitted = st.form_submit_button("Get Summary", type="primary")

# --- Processing and Output ---
if submitted:
    if not topic_url:
        st.error("Please enter a Nairaland URL.")
    elif "nairaland.com" not in topic_url:
        st.error("Please enter a valid Nairaland.com URL.")
    else:
        with st.spinner("Working on it... This might take a moment..."):
            # 1. Get URLs
            list_of_page_urls = get_page_urls_to_scrape(topic_url, pages_to_scrape_count)

            # 2. Scrape Posts
            all_scraped_posts = []
            progress_bar = st.progress(0, text="Scraping pages...")
            for i, url in enumerate(list_of_page_urls):
                st.toast(f"Fetching page {i+1}/{len(list_of_page_urls)}...")
                posts_on_page = fetch_and_parse_url(url)
                if posts_on_page:
                    all_scraped_posts.extend(posts_on_page)
                progress_bar.progress((i + 1) / len(list_of_page_urls), text=f"Scraping page {i+1}")
            
            progress_bar.empty()

            if all_scraped_posts:
                st.info(f"Found {len(all_scraped_posts)} posts across {len(list_of_page_urls)} page(s).")
                
                # 3. Format Posts and Summarize
                with st.spinner("Asking the AI for a summary..."):
                    formatted_text = format_posts_for_llm(all_scraped_posts)
                    summary = summarize_with_gemini(formatted_text)
                
                # 4. Display Result
                st.success("Summary Complete!")
                st.markdown("---")
                st.markdown(summary)
            else:
                st.error("No posts were found. Please check the URL or try again later.")

st.markdown("---")
