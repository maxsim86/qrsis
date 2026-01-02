from django.shortcuts import render, redirect, get_object_or_404
from .models import Queue, Visitor
from django.db.models import Max
import qrcode
from io import BytesIO
import base64
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db import transaction



def kiosk_join(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # Jika queue tutup/penuh
    if not queue.allow_join:
        return render(request, 'queues/disabled.html')
    
    # Logic POST (Bila user tekan 'Get Ticket')
    if request.method == "POST":
        last_visitor = Visitor.objects.filter(queue=queue).aggregate(Max('number'))
        next_number = (last_visitor['number__max'] or 0) + 1
        
        # Ambil nama dari input atau guna default
        custom_name = request.POST.get('name')
        
        # Jika setting "Ask Input" OFF, kita set nama default
        if not queue.ask_input:
             visitor_name = f"Visitor #{next_number}"
        else:
             visitor_name = custom_name if custom_name else f"Visitor #{next_number}"
        
        new_visitor = Visitor.objects.create(
            queue=queue, 
            name=visitor_name, 
            number=next_number,
            status='WAITING'
        )

        # Hantar Signal ke TV/Admin
        send_socket_update(slug, 'new_visitor', {
            'visitor_id': new_visitor.id,
            'number': f"{new_visitor.number:03d}",
            'name': new_visitor.name
        })
        
        # PENTING: Jangan redirect ke 'visitor_status'.
        # Render semula page kiosk tapi dengan data tiket baru.
        return render(request, 'queues/kiosk.html', {
            'queue': queue,
            'new_ticket': new_visitor, # Data untuk popup sukses
            'success_mode': True
        })
        
    return render(request, 'queues/kiosk.html', {'queue': queue})


def send_socket_update(slug, event_type, extra_data=None):
    channel_layer = get_channel_layer()
    
    # Kita automatik ambil data queue terkini setiap kali signal dihantar
    queue = Queue.objects.get(slug=slug)
    realtime_data = get_realtime_data(queue)
    
    # Gabungkan data manual (contoh: info orang yg dipanggil) dengan data realtime
    final_data = {**realtime_data, **(extra_data or {})}

    async_to_sync(channel_layer.group_send)(
        f'queue_{slug}',
        {
            'type': 'queue_update',
            'message': event_type,
            'data': final_data
        }
    )
    
    
def set_counter(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    if request.method == "POST":
        # Ambil nama dari input (cth: "Kaunter 1" atau "Bilik Rawatan 2")
        counter_name = request.POST.get('counter_name')
        
        # Simpan dalam session browser ini sahaja
        request.session['counter_name'] = counter_name
        
        return redirect('admin_interface', slug=slug)
        
    return render(request, 'queues/set_counter.html', {'queue': queue})


def update_queue_settings(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    if request.method == "POST":
        queue.name = request.POST.get('name')
        queue.allow_join = request.POST.get('allow_join') == 'on'
        # Update Ask Input & Label
        queue.ask_input = request.POST.get('ask_input') == 'on'
        queue.input_label = request.POST.get('input_label')
        queue.capacity = request.POST.get('capacity')
        queue.wait_time_display = request.POST.get('wait_time_display')
        queue.status_language = request.POST.get('status_language')
        # Ambil nilai dari form, jika kosong set default 1000
        cap = request.POST.get('capacity')
        if cap:
            queue.capacity = int(cap)
        
        queue.save()
        messages.success(request, "Queue settings updated!")
        
    return redirect('admin_interface', slug=slug)



def create_queue(request):
    if request.method == "POST":
        name = request.POST.get('name')
        ask_input = request.POST.get('ask_input') 
        if ask_input == 'on':
            label = request.POST.get('label') or "Masukkan nama anda"
        else:
            label = "" 
        new_queue = Queue.objects.create(name=name, input_label=label)
        return redirect('dashboard', slug=new_queue.slug)
    return render(request, 'queues/create.html')

# 2. Page Dashboard lepas create (Screenshot 2)
def dashboard(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
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
    join_url = f"http://{request.get_host()}/q/{slug}/join/"
    
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(join_url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    buffer = BytesIO()
    img.save(buffer)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'queues/poster.html', {'queue': queue, 'qr_code': img_str, 'join_url': join_url})

def visitor_join(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # --- LOGIK BARU: SEMAK STATUS SELF-SIGN-IN ---
    if not queue.allow_join:
        # Jika Disabled, terus tunjuk page disabled
        return render(request, 'queues/disabled.html')
    
    current_waiting = Visitor.objects.filter(queue=queue, status='WAITING').count()
    
    if current_waiting >= queue.capacity:
        # Jika dah penuh, tunjuk page 'Full'
        return render(request, 'queues/full.html')
    
    
    if request.method == "POST":
        # ... (kod lama untuk create visitor kekal sama) ...
        last_visitor = Visitor.objects.filter(queue=queue).aggregate(Max('number'))
        next_number = (last_visitor['number__max'] or 0) + 1
        
        if queue.input_label:
            name = request.POST.get('name')
        else:
            name = f"Visitor #{next_number}"
        
        new_visitor = Visitor.objects.create(
            queue=queue, 
            name=name, 
            number=next_number,
            status='WAITING'
        )

        send_socket_update(slug, 'new_visitor', {
            'visitor_id': new_visitor.id,
            'number': f"{new_visitor.number:03d}",
            'name': new_visitor.name
        })
        
        return redirect('visitor_status', visitor_id=new_visitor.id)
        
    return render(request, 'queues/join.html', {'queue': queue})


# 2. Page Status (Bulatan Biru)
def visitor_status(request, visitor_id):
    try:
        visitor = Visitor.objects.get(id=visitor_id)
    except Visitor.DoesNotExist:   
        return render(request, 'queues/session_ended.html')
    
    queue = visitor.queue
    
    if visitor.status == 'WAITING':
        people_ahead = Visitor.objects.filter(
            queue=queue, 
            status='WAITING', 
            id__lt=visitor.id
        ).count()
        position = people_ahead + 1
        
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
    visitor.delete()
    
    # --- TAMBAH SIGNAL DI SINI ---
    # Supaya Admin tahu ada orang keluar queue (Update Counter tolak 1)
    send_socket_update(queue_slug, 'visitor_quit', {})

    return redirect('visitor_join', slug=queue_slug)

def admin_interface(request, slug):
    # 1. Check dulu ada tak counter name dalam session?
    if 'counter_name' not in request.session:
        return redirect('set_counter', slug=slug) # Kalau tak ada, paksa set nama dulu
    queue = get_object_or_404(Queue, slug=slug)
    current_counter_name = request.session['counter_name']
    current_serving = Visitor.objects.filter(queue=queue, status='SERVING').first()
    
    # Kita ambil SEMUA waiting visitor untuk dipaparkan dalam MODAL "Choose Visitor"
    all_waiting_visitors = Visitor.objects.filter(queue=queue, status='WAITING').order_by('id')
    
    waiting_count = all_waiting_visitors.count()
    next_visitor = all_waiting_visitors.first()
    last_visitor = Visitor.objects.filter(queue=queue).aggregate(Max('number'))
    next_new_number = (last_visitor['number__max'] or 0) + 1
    
    return render(request, 'queues/admin.html', {
        'queue': queue,
        'current_serving': current_serving,
        'waiting_count': waiting_count,
        'next_visitor': next_visitor,
        'all_waiting_visitors': all_waiting_visitors, # PASS KE TEMPLATE UNTUK MODAL
        'next_new_number': next_new_number,
        'current_counter_name': current_counter_name,
    })
    

def add_manual_visitor(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # Kira nombor seterusnya
    last_visitor = Visitor.objects.filter(queue=queue).aggregate(Max('number'))
    next_number = (last_visitor['number__max'] or 0) + 1
    
    # LOGIK BARU: Cek jika ada nama dihantar dari form
    custom_name = request.POST.get('custom_name')
    
    if custom_name:
        # Jika admin isi nama, guna nama tu
        visitor_name = custom_name
    else:
        # Jika tak isi (atau setting OFF), guna nama default
        visitor_name = f"Visitor #{next_number}"
    
    # Create Visitor
    new_visitor = Visitor.objects.create(
        queue=queue,
        name=visitor_name,
        number=next_number,
        status='WAITING'
    )
    
    messages.success(request, f"Added {visitor_name} (#{next_number:03d})")
    
    # Hantar Signal WebSocket
    send_socket_update(slug, 'new_visitor', {
        'visitor_id': new_visitor.id,
        'number': f"{new_visitor.number:03d}",
        'name': new_visitor.name
    })

    return redirect('admin_interface', slug=slug)

    
def acknowledge_return(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    visitor.is_returned = False 
    visitor.save()
    return redirect('visitor_status', visitor_id=visitor.id)
    
def return_to_queue(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    slug = visitor.queue.slug
    
    # 1. Update Database
    visitor.status = 'WAITING'
    visitor.is_returned = True
    visitor.save()
    
    # 2. HANTAR SIGNAL WEBSOCKET
    # Kita hantar 'current_number': '000' untuk reset display
    send_socket_update(slug, 'return_queue', {
        'visitor_id': visitor.id,
        'returned_number': f"{visitor.number:03d}",
        'returned_name': visitor.name
    })
    
    return redirect('admin_interface', slug=slug)

def remove_visitors(request, slug):
    # Fungsi: Kosongkan semua visitor dalam queue ini (Reset)
    queue = get_object_or_404(Queue, slug=slug)
    if request.method == "POST":
        Visitor.objects.filter(queue=queue).delete()
        # Beritahu TV display untuk reset ke 000
        send_socket_update(slug, 'queue_reset', {})
    return redirect('admin_interface', slug=slug)

def remove_specific_visitor(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    slug = visitor.queue.slug
    
    # 1. Padam Visitor
    visitor.delete()
    
    # 2. Hantar Signal WebSocket (Update List & Counter)
    # Kita guna signal 'queue_reset' atau 'visitor_quit' pun boleh, 
    # asalkan frontend refresh list.
    send_socket_update(slug, 'visitor_quit', {})
    
    return redirect('admin_interface', slug=slug)

def call_next(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    counter_name = request.session.get('counter_name', 'General Counter')
    current = Visitor.objects.filter(queue=queue, status='SERVING').first()
    if current:
        current.status = 'COMPLETED'
        current.save()
        
    #next_visitor = Visitor.objects.filter(queue=queue, status='WAITING').order_by('id').first()
    with transaction.atomic():
        next_visitor = Visitor.objects.filter(queue=queue, status='WAITING').select_for_update().order_by('id').first()
        
    if next_visitor:
        next_visitor.status = 'SERVING'
        next_visitor.served_by = counter_name
        next_visitor.is_invited = True
        next_visitor.save()
        
        # SIGNAL SEDIA ADA (BETUL)
        send_socket_update(slug, 'invite_next', {
            'visitor_id': next_visitor.id,
            'number': f"{next_visitor.number:03d}",
            'name': next_visitor.name,
            'counter': counter_name,
        })
        
    return redirect('admin_interface', slug=slug)


def acknowledge_invite(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    visitor.is_invited = False
    visitor.save()
    return redirect('visitor_status', visitor_id=visitor.id)

# 6. Page Status Display TV (Screenshot 1 - Display)
def status_display(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    current_serving = Visitor.objects.filter(queue=queue, status='SERVING').first()
    
    return render(request, 'queues/display.html', {
        'queue': queue,
        'current_serving': current_serving
    })
    
#Dapatkan Data Real-time
def get_realtime_data(queue):
    """
    Helper untuk ambil data terkini queue supaya boleh dihantar ke WebSocket
    """
    waiting_visitors = Visitor.objects.filter(queue=queue, status='WAITING').order_by('id')
    waiting_count = waiting_visitors.count()
    
    # Ambil 3 orang seterusnya untuk dipaparkan di TV
    next_3_visitors = [f"{v.number:03d}" for v in waiting_visitors[:3]]
    
    return {
        'waiting_count': waiting_count,
        'next_visitors': next_3_visitors
    }
    
def invite_specific_visitor(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    queue = visitor.queue
    slug = queue.slug

    # 1. Selesaikan orang semasa (jika ada)
    current = Visitor.objects.filter(queue=queue, status='SERVING').first()
    if current:
        current.status = 'COMPLETED'
        current.save()

    # 2. Set pelawat yang DIPILIH sebagai serving
    visitor.status = 'SERVING'
    visitor.is_invited = True
    visitor.save()

    # 3. Hantar Signal (Logic ini automatik update list next visitors di TV)
    send_socket_update(slug, 'invite_next', {
        'visitor_id': visitor.id,
        'number': f"{visitor.number:03d}",
        'name': visitor.name
    })

    return redirect('admin_interface', slug=slug)