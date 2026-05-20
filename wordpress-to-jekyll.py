#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import re
from html import unescape
from datetime import datetime
import os
from pathlib import Path

# WordPress namespace
ns = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/'
}

def wp_to_jekyll_slug(title):
    """Convert title to Jekyll slug"""
    # Remove emojis and special chars, replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', title)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = slug.lower().strip('-')
    return slug

def convert_wp_content_to_markdown(html_content):
    """Convert WordPress HTML content to Markdown"""
    if not html_content:
        return ""

    # Unescape HTML entities
    text = unescape(html_content)

    # Convert WordPress blocks to simple markdown
    # Remove WordPress-specific comments and block markers
    text = re.sub(r'<!-- wp:[\w\s"-:]+ -->', '', text)
    text = re.sub(r'<!-- /wp:\w+ -->', '', text)
    text = re.sub(r'<!-- wp:\w+ -->', '', text)

    # Convert paragraphs
    text = re.sub(r'<p[^>]*>', '', text)
    text = re.sub(r'</p>', '\n\n', text)

    # Convert headings
    text = re.sub(r'<h([1-6])[^>]*>', lambda m: '\n' + '#' * int(m.group(1)) + ' ', text)
    text = re.sub(r'</h[1-6]>', '\n', text)

    # Convert bold and italic
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)

    # Convert links
    text = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)

    # Convert lists
    text = re.sub(r'<ul[^>]*>', '\n', text)
    text = re.sub(r'</ul>', '\n', text)
    text = re.sub(r'<ol[^>]*>', '\n', text)
    text = re.sub(r'</ol>', '\n', text)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL)

    # Convert blockquotes
    text = re.sub(r'<blockquote[^>]*>', '> ', text)
    text = re.sub(r'</blockquote>', '\n', text)

    # Convert code blocks
    text = re.sub(r'<pre[^>]*><code[^>]*>', '```\n', text)
    text = re.sub(r'</code></pre>', '\n```', text)
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)

    # Convert line breaks
    text = re.sub(r'<br[^>]*>', '\n', text)

    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def create_jekyll_front_matter(post_data):
    """Create Jekyll front matter"""
    date = datetime.strptime(post_data['date'], '%Y-%m-%d %H:%M:%S')
    formatted_date = date.strftime('%Y-%m-%d %H:%M:%S')

    slug = wp_to_jekyll_slug(post_data['title'])

    front_matter = f"""---
title: "{post_data['title']}"
date: {formatted_date} +0800
categories:
tags:
---

"""
    return front_matter

def extract_posts(xml_file):
    """Extract all posts from WordPress XML export"""
    tree = ET.parse(xml_file)
    posts = []

    for item in tree.findall('.//item'):
        post_type = item.find('wp:post_type', ns)
        if post_type is None or post_type.text != 'post':
            continue

        title_elem = item.find('title', ns)
        link_elem = item.find('link', ns)
        date_elem = item.find('wp:post_date', ns)
        content_elem = item.find('content:encoded', ns)

        title = unescape(title_elem.text) if title_elem is not None and title_elem.text else ''
        link = link_elem.text if link_elem is not None else ''
        date = date_elem.text if date_elem is not None else ''
        content = content_elem.text if content_elem is not None else ''

        # Skip very short or empty posts
        if len(content) < 50:
            continue

        # Skip default WordPress posts
        if title in ['網站第一篇文章', '範例頁面', '隱私權政策']:
            continue

        posts.append({
            'title': title,
            'link': link,
            'date': date,
            'content': content
        })

    return posts

def main():
    xml_file = 'docker.WordPress.2026-05-20.xml'
    output_dir = Path('_posts')
    output_dir.mkdir(exist_ok=True)

    posts = extract_posts(xml_file)
    print(f"找到 {len(posts)} 篇文章\n")

    for i, post in enumerate(posts, 1):
        date = datetime.strptime(post['date'], '%Y-%m-%d %H:%M:%S')
        slug = wp_to_jekyll_slug(post['title'])
        filename = f"{date.strftime('%Y-%m-%d')}-{slug}.md"

        front_matter = create_jekyll_front_matter(post)
        markdown_content = convert_wp_content_to_markdown(post['content'])

        output_path = output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(front_matter + markdown_content)

        print(f"{i}. {filename}")
        print(f"   標題: {post['title']}")

    print(f"\n完成！已匯出 {len(posts)} 篇文章到 _posts/ 目錄")

if __name__ == '__main__':
    main()