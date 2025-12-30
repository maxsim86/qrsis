from django.shortcuts import render, redirect, get_object_or_404
from .models import Queue, Visitor
from django.db.models import Max
import qrcode
from io import BytesIO
import base64
from django.core.exceptions import ObjectDoesNotExist


def create_queue(request):
    if request.method == "POST":
        name = request.POST.get('name')
        
        # Semak status Toggle (checkbox)
        # HTML checkbox hantar 'on' jika dicentang, atau None jika tidak.
        ask_input = request.POST.get('ask_input') 
        
        if ask_input == 'on':
            # Jika Toggle ON, ambil input label user, atau guna default
            label = request.POST.get('label') or "Masukkan nama anda"
        else:
            # Jika Toggle OFF, set label jadi Kosong String
            label = "" 

        new_queue = Queue.objects.create(name=name, input_label=label)
        return redirect('dashboard', slug=new_queue.slug)
        
    return render(request, 'queues/create.html')

# 2. Page Dashboard lepas create (Screenshot 2)
def dashboard(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # Bina URL penuh menggunakan request.build_absolute_uri
    base_url = f"{request.scheme}://{request.get_host()}"
    
    context = {
        'queue': queue,
        'visitor_url': f"{base_url}/q/{slug}/join/",
        'poster_url': f"{base_url}/q/{slug}/poster/",
        'admin_url': f"{base_url}/q/{slug}/admin/",
        'display_url': f"{base_url}/q/{slug}/display/",
    }
    return render(request, 'queues/dashboard.html', context)

# 3. Page untuk Print QR Poster (Screenshot 3)
def poster_view(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    # Generate Link
    join_url = f"http://{request.get_host()}/q/{slug}/join/"
    
    # Generate QR Image
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(join_url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    # Convert image ke base64 string untuk display di HTML
    buffer = BytesIO()
    img.save(buffer)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'queues/poster.html', {'queue': queue, 'qr_code': img_str, 'join_url': join_url})

# 1. Page Masukkan Nama (Join)
def visitor_join(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    if request.method == "POST":
        # Logic nombor giliran (Kekal sama)
        last_visitor = Visitor.objects.filter(queue=queue).aggregate(Max('number'))
        next_number = (last_visitor['number__max'] or 0) + 1
        
        # LOGIC BARU: Tentukan Nama
        if queue.input_label:
            # Jika ada label, maksudnya user kena isi nama
            name = request.POST.get('name')
        else:
            # Jika tiada label (Toggle OFF), kita bagi nama automatik
            name = f"Visitor #{next_number}"
        
        new_visitor = Visitor.objects.create(
            queue=queue, 
            name=name, 
            number=next_number,
            status='WAITING'
        )
        return redirect('visitor_status', visitor_id=new_visitor.id)
        
    return render(request, 'queues/join.html', {'queue': queue})


# 2. Page Status (Bulatan Biru)
def visitor_status(request, visitor_id):
    try:
        visitor = Visitor.objects.get(id=visitor_id)
    except Visitor.DoesNotExist:   
        return render(request, 'queues/session_ended.html')
    queue = visitor.queue
    
    # Logic: Kira berapa orang 'WAITING' yang join SEBELUM visitor ini
    if visitor.status == 'WAITING':
        people_ahead = Visitor.objects.filter(
            queue=queue, 
            status='WAITING', 
            id__lt=visitor.id # id less than current visitor
        ).count()
        position = people_ahead + 1 # +1 sebab diri sendiri
        
        # Tentukan suffix (1st, 2nd, 3rd, 4th)
        if 10 <= position % 100 <= 20: suffix = 'th'
        else: suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(position % 10, 'th')
        
        position_text = f"{position}{suffix}"
    else:
        position_text = "-"

    context = {
        'visitor': visitor,
        'queue': queue,
        'position_text': position_text
    }
    return render(request, 'queues/ticket.html', context)

# 3. Function Quit Queue
def visitor_quit(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    queue_slug = visitor.queue.slug
    
    # Delete visitor dari database
    visitor.delete()
    
    # Redirect balik ke page join
    return redirect('visitor_join', slug=queue_slug)

def admin_interface(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # Dapatkan visitor yang sedang dilayan (SERVING)
    current_serving = Visitor.objects.filter(queue=queue, status='SERVING').first()
    
    # Kira berapa orang menunggu
    waiting_count = Visitor.objects.filter(queue=queue, status='WAITING').count()
    
    return render(request, 'queues/admin.html', {
        'queue': queue,
        'current_serving': current_serving,
        'waiting_count': waiting_count
    })
    
    
def acknowledge_return(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    
    # User dah tekan "Good", so kita padam flag return
    visitor.is_returned = False 
    visitor.save()
    
    return redirect('visitor_status', visitor_id=visitor.id)
    
def return_to_queue(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    visitor.status = 'WAITING'
    visitor.is_returned = True  # Setkan flag ini jadi True
    visitor.save()
    return redirect('admin_interface', slug=visitor.queue.slug)

def remove_visitors(request, slug):
    # Fungsi: Kosongkan semua visitor dalam queue ini (Reset)
    queue = get_object_or_404(Queue, slug=slug)
    if request.method == "POST":
        Visitor.objects.filter(queue=queue).delete()
    return redirect('admin_interface', slug=slug)

# Logic Button "Invite Next"
def call_next(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # Set current serving kepada COMPLETED
    current = Visitor.objects.filter(queue=queue, status='SERVING').first()
    if current:
        current.status = 'COMPLETED'
        current.save()
        
    # Ambil next waiting visitor
    next_visitor = Visitor.objects.filter(queue=queue, status='WAITING').order_by('id').first()
    if next_visitor:
        next_visitor.status = 'SERVING'
        next_visitor.save()
        
    return redirect('admin_interface', slug=slug)

# 6. Page Status Display TV (Screenshot 1 - Display)
def status_display(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    current_serving = Visitor.objects.filter(queue=queue, status='SERVING').first()
    
    return render(request, 'queues/display.html', {
        'queue': queue,
        'current_serving': current_serving
    })