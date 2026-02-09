import re
from django import template

register = template.Library()
@register.filter(name='youtube_embed')
def youtube_embed(url):
    if not url:
        return ""

    # Regex untuk cari Video ID (Sokong: youtu.be, youtube.com/watch, youtube.com/embed)
    regex = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
    match = re.search(regex, url)

    if match:
        video_id = match.group(1)
        return f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=1&mute=1&controls=0&showinfo=0&rel=0&loop=1&playlist={video_id}"
    
    return url