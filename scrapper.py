import streamlit as st
import requests
import pandas as pd
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
import io
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Nairaland Topic Scraper",
    layout="wide"
)

def get_clean_topic_url(url):
    """Helper function to strip page numbers from a URL."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    clean_path = '/' + '/'.join(path_parts[:2])
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, '', '', ''))

def get_page_urls_to_scrape(topic_url, num_pages_to_scrape=1):
    """Finds the URLs for the last 'n' pages of a Nairaland topic."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(get_clean_topic_url(topic_url), headers=headers, timeout=15)
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
                try:
                    num = int(tag_text.strip('()'))
                    if num > last_page_num: 
                        last_page_num = num
                except ValueError: 
                    continue
        last_page_num = max(1, last_page_num)
        start_page = max(1, last_page_num - num_pages_to_scrape + 1)
        urls_to_scrape = []
        base_url = get_clean_topic_url(topic_url)
        
        for page_num in range(start_page, last_page_num + 1):
            if page_num == 1: 
                urls_to_scrape.append(base_url)
            else: 
                urls_to_scrape.append(f"{base_url}/{page_num - 1}")
        return urls_to_scrape
    except requests.exceptions.RequestException as e:
        st.error(f"Error finding pages: {e}")
        return [get_clean_topic_url(topic_url)]

def parse_html_content(html_content, page_url):
    """Parses Nairaland HTML to extract posts, separating original text from quotes."""
    soup = BeautifulSoup(html_content, 'lxml')
    posts_data = []
    posts_table = soup.find('table', summary='posts')
    if not posts_table: 
        return []
    post_bodies = posts_table.find_all('td', class_='l w pd')
    for post_body in post_bodies:
        narrow_div = post_body.find('div', class_='narrow')
        if not narrow_div: 
            continue
        quotes = []
        for quote in narrow_div.find_all('blockquote'):
            quotes.append(quote.get_text(separator=' ', strip=True))
            quote.decompose()
        post_text = narrow_div.get_text(separator=' ', strip=True)
        if not post_text: 
            continue
        header_row = post_body.find_parent('tr').find_previous_sibling('tr')
        if not header_row: 
            continue
        author_tag = header_row.find('a', class_='user')
        author = author_tag.get_text(strip=True) if author_tag else "Unknown"
        
        post_id_tag = header_row.find('a', attrs={'name': lambda x: x and x.startswith('msg')})
        if post_id_tag:
            post_id = post_id_tag['name'].replace('msg', '')
            post_link = f"{page_url}#{post_id}"
        else:
            post_link = page_url
            
        # Format quoted posts as specified
        quoted_posts_str = " || ".join(quotes) if quotes else ""
        
        posts_data.append({
            'author': author, 
            'post_text': post_text, 
            'quoted_posts': quoted_posts_str, 
            'link': post_link
        })
    return posts_data

def fetch_and_parse_url(url):
    """Fetches and parses a URL for Nairaland posts."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return parse_html_content(response.text, url)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL {url}: {e}")
        return []

def scrape_nairaland_topic(topic_url, num_pages):
    """Main scraping function."""
    # Get URLs to scrape
    page_urls = get_page_urls_to_scrape(topic_url, num_pages)
    
    # Scrape posts from all pages
    all_posts = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, url in enumerate(page_urls):
        status_text.text(f"Scraping page {i+1} of {len(page_urls)}...")
        progress_bar.progress((i + 1) / len(page_urls))
        
        posts = fetch_and_parse_url(url)
        all_posts.extend(posts)
    
    status_text.text(f"Scraping complete! Found {len(all_posts)} posts.")
    return all_posts

def main():
    st.title("Nairaland Topic Scraper")
    st.markdown("Extract forum posts from Nairaland topics for market research and social media content analysis.")
    
    # Sidebar for inputs
    st.sidebar.header("Scraping Parameters")
    
    # URL input
    topic_url = st.sidebar.text_input(
        "Nairaland Topic URL",
        placeholder="https://www.nairaland.com/8458824/topic-name",
        help="Enter the full URL of the Nairaland topic you want to scrape"
    )
    
    # Number of pages input
    num_pages = st.sidebar.number_input(
        "Number of Pages to Scrape",
        min_value=1,
        max_value=50,
        value=2,
        help="Number of most recent pages to scrape (starting from the last page)"
    )
    
    # Scrape button
    if st.sidebar.button("Start Scraping", type="primary"):
        if not topic_url:
            st.error("Please enter a Nairaland topic URL")
            return
        
        if not topic_url.startswith("https://www.nairaland.com/"):
            st.error("Please enter a valid Nairaland URL")
            return
        
        with st.spinner("Scraping in progress..."):
            posts = scrape_nairaland_topic(topic_url, num_pages)
        
        if posts:
            st.success(f"Successfully scraped {len(posts)} posts!")
            
            # Store data in session state for download
            st.session_state.scraped_data = posts
            st.session_state.topic_url = topic_url
            
            # Display preview
            st.subheader("📊 Data Preview")
            
            # Show summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Posts", len(posts))
            with col2:
                unique_authors = len(set(post['author'] for post in posts))
                st.metric("Unique Authors", unique_authors)
            with col3:
                posts_with_quotes = len([p for p in posts if p['quoted_posts']])
                st.metric("Posts with Quotes", posts_with_quotes)
            
            # Show sample data
            df = pd.DataFrame(posts)
            st.dataframe(df.head(10), use_container_width=True)
            
            if len(posts) > 10:
                st.info(f"Showing first 10 posts. Total: {len(posts)} posts")
        else:
            st.error("No posts were found. Please check the URL and try again.")
    
    # Download section
    if 'scraped_data' in st.session_state:
        st.subheader("Download Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV download
            df = pd.DataFrame(st.session_state.scraped_data)
            csv = df.to_csv(index=False)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_csv = f"nairaland_posts_{timestamp}.csv"
            
            st.download_button(
                label="📄 Download as CSV",
                data=csv,
                file_name=filename_csv,
                mime="text/csv",
                help="Download data as CSV file for Excel/Google Sheets"
            )
        
        with col2:
            # JSON download
            json_data = json.dumps(st.session_state.scraped_data, indent=2)
            filename_json = f"nairaland_posts_{timestamp}.json"
            
            st.download_button(
                label="📋 Download as JSON",
                data=json_data,
                file_name=filename_json,
                mime="application/json",
                help="Download data as JSON file for programming/LLM analysis"
            )
        
        # Show data structure example
        st.subheader("Data Structure")
        st.markdown("Each post is structured as follows:")
        example_post = {
            'author': 'JohnDoe',
            'post_text': 'This is my opinion on the matter...',
            'quoted_posts': 'Quote 1 || Quote 2',
            'link': 'https://nairaland.com/12345#msg67890'
        }
        st.code(json.dumps(example_post, indent=2), language='json')
    
    # Usage instructions
    st.subheader("How to Use")
    st.markdown("""
    1. **Enter URL**: Paste the Nairaland topic URL you want to scrape
    2. **Set Pages**: Choose how many recent pages to scrape (default: 2)
    3. **Scrape**: Click "Start Scraping" to begin extraction
    4. **Download**: Export your data as CSV or JSON for further analysis
    
    **Perfect for**: Market research, social media content planning, audience insights, and LLM analysis.
    """)

if __name__ == "__main__":
    main()