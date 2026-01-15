from django.shortcuts import render, redirect, get_object_or_404
from .models import Queue, Visitor
from django.db.models import Max
import qrcode
from io import BytesIO
import base64
from django.contrib import messages
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
#from asgiref.sync import sync_to_async
from django.db import transaction
from django.http import HttpResponse
import re
import json
from django.db.models import Count
from django.utils import timezone
from django.db.models.functions import ExtractHour



def admin_remote(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # Dapatkan status terkini untuk dipaparkan di remote
    current_serving = Visitor.objects.filter(queue=queue, status='SERVING').last()
    waiting_count = Visitor.objects.filter(queue=queue, status='WAITING').count()
    next_visitor = Visitor.objects.filter(queue=queue, status='WAITING').order_by('id').first()

    context = {
        'queue': queue,
        'current_serving': current_serving,
        'waiting_count': waiting_count,
        'next_visitor': next_visitor,
    }
    return render(request, 'queues/admin_remote.html', context)


def queue_stats(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    # 1. Ambil pelawat HARI INI sahaja
    today = timezone.now().date()
    visitors_today = Visitor.objects.filter(queue=queue, joined_at__date=today)
    
    # 2. Statistik Asas
    total_today = visitors_today.count()
    completed_count = visitors_today.filter(status='COMPLETED').count()
    waiting_count = visitors_today.filter(status='WAITING').count()
    serving_count = visitors_today.filter(status='SERVING').count()
    
    # 3. Statistik Mengikut Servis (A, B, C)
    count_a = visitors_today.filter(service_type='A').count()
    count_b = visitors_today.filter(service_type='B').count()
    count_c = visitors_today.filter(service_type='C').count()
    
    # 4. Data untuk Carta 1 & 2
    chart_service_data = [count_a, count_b, count_c]
    chart_status_data = [completed_count, serving_count, waiting_count]

    # --- 5. LOGIK BARU: WAKTU PUNCAK (PEAK HOURS) ---
    # Kira berapa orang datang pada pukul 8, 9, 10, dll.
    peak_data = visitors_today.annotate(hour=ExtractHour('joined_at')) \
                              .values('hour') \
                              .annotate(count=Count('id')) \
                              .order_by('hour')
    
    # Sediakan label jam (8:00 - 17:00)
    # Ini create list: ["8:00", "9:00", ... "17:00"]
    hours_labels = [f"{h}:00" for h in range(8, 18)] 
    
    # Sediakan data kosong (0 pelawat untuk setiap jam)
    hours_data = [0] * 10 
    
    # Isi data sebenar ke dalam slot jam yang betul
    for item in peak_data:
        h = item['hour']
        # Pastikan jam berada dalam lingkungan ofis (8am - 5pm)
        if 8 <= h < 18:
            index = h - 8 # Contoh: Pukul 8 tolak 8 = index 0
            hours_data[index] = item['count']

    context = {
        'queue': queue,
        'today': today,
        'total_today': total_today,
        # Data Carta Asal
        'chart_service_data': json.dumps(chart_service_data),
        'chart_status_data': json.dumps(chart_status_data),
        # Data Carta Baru (Waktu Puncak)
        'chart_hours_labels': json.dumps(hours_labels),
        'chart_hours_data': json.dumps(hours_data),
    }
    
    return render(request, 'queues/stats.html', context)


def get_ticket_format(visitor):
    return f"{visitor.service_type}{visitor.number:03d}"


def search_visitors(request, slug):
    query = request.GET.get('q')
    service_filter = request.GET.get('type') # <--- TAMBAH INI (Ambil parameter filter)
    queue = get_object_or_404(Queue, slug=slug)
    
    visitors = Visitor.objects.filter(queue=queue, status='WAITING').order_by('is_returned', 'id')
    
    # 1. Filter ikut Service Type (A/B/C) jika butang ditekan
    if service_filter and service_filter != 'ALL':
        visitors = visitors.filter(service_type=service_filter)

    # 2. Filter ikut Carian Nombor/Nama
    if query:
        clean_query = re.sub(r'\D', '', query)
        if clean_query:
            visitors = visitors.filter(number__icontains=clean_query)
        else:
            visitors = visitors.filter(name__icontains=query)
        
    return render(request, 'queues/partials/visitor_list.html', {
        'all_waiting_visitors': visitors
    })
    
    
    
    

def get_admin_updates(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    # Dapatkan data terkini
    current_serving = Visitor.objects.filter(queue=queue, status='SERVING').first()
    all_waiting_visitors = Visitor.objects.filter(queue=queue, status='WAITING') \
                                          .order_by('is_returned', 'id')
    waiting_count = all_waiting_visitors.count()
    
    # Kira nombor pelawat seterusnya (untuk button Call Next)
    next_visitor = all_waiting_visitors.first()

    context = {
        'queue': queue,
        'current_serving': current_serving,
        'all_waiting_visitors': all_waiting_visitors,
        'waiting_count': waiting_count,
        'next_visitor': next_visitor,
    }
    
    # Render fail partial (kita akan buat fail ini di Langkah 4)
    return render(request, 'queues/partials/admin_board.html', context)


def kiosk_join(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    
    if not queue.allow_join:
        return render(request, 'queues/disabled.html')
    
    if request.method == "POST":
        # 1. Ambil Service Type dari butang yang ditekan (default 'A')
        service_type = request.POST.get('service_type', 'A')

        # 2. Kira Max Number BERDASARKAN SERVICE TYPE itu sahaja
        last_visitor = Visitor.objects.filter(queue=queue, service_type=service_type).aggregate(Max('number'))
        next_number = (last_visitor['number__max'] or 0) + 1
        
        # 3. Tentukan Nama
        if queue.ask_input:
            custom_name = request.POST.get('name')
            # Guna format baru A001 dalam nama default
            visitor_name = custom_name if custom_name else f"Visitor #{service_type}{next_number:03d}"
        else:
            visitor_name = f"Visitor #{service_type}{next_number:03d}"
        
        # 4. Create Visitor
        new_visitor = Visitor.objects.create(
            queue=queue, 
            name=visitor_name, 
            number=next_number,
            service_type=service_type, # Simpan jenis servis
            status='WAITING'
        )

        # 5. Socket Update (Guna format tiket baru)
        send_socket_update(slug, 'new_visitor', {
            'visitor_id': new_visitor.id,
            'ticket': new_visitor.ticket_number, # Guna property dari model
            'number': new_visitor.ticket_number,
            'name': new_visitor.name
        })
        
        if request.headers.get('HX-Request'):
            return render(request, 'queues/partials/kiosk_ticket_partial.html', {
                'new_ticket': new_visitor
            })
        
        return render(request, 'queues/kiosk.html', {
            'queue': queue,
            'new_ticket': new_visitor,
            'success_mode': True
        })
    
    if request.headers.get('HX-Request'):
         return render(request, 'queues/partials/kiosk_form_partial.html', {'queue': queue})
    
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
        # 1. Update Text Fields
        queue.name = request.POST.get('name')
        queue.allow_join = request.POST.get('allow_join') == 'on'
        queue.ask_input = request.POST.get('ask_input') == 'on'
        raw_label = request.POST.get('input_label')

        if raw_label:
            queue.input_label = raw_label
        else:
            queue.input_label = "Enter your name"
        # --------------------------
        
        # 2. Update Dropdowns (Default ke AUTO jika kosong)
        queue.wait_time_display = request.POST.get('wait_time_display') or 'AUTO'
        queue.status_language = request.POST.get('status_language') or 'AUTO'

        # 3. Update Capacity (Safety Check)
        cap = request.POST.get('capacity')
        if cap:
            try:
                queue.capacity = int(cap)
            except ValueError:
                queue.capacity = 50 
        else:
            queue.capacity = 50

        # 4. HANDLE LOGO UPLOAD (INI YANG ANDA TERTINGGAL)
        # Kita mesti cek request.FILES untuk ambil gambar
        if request.FILES.get('logo'):
            queue.logo = request.FILES['logo']

        # 5. Remove Logo Checkbox
        if request.POST.get('remove_logo') == 'on':
            queue.logo = None
        
        queue.save()
        messages.success(request, "Queue settings updated!")

    if request.headers.get('HX-Request'):
        messages.success(request, "Settings Saved!")
        # Return partial form settings sahaja
        return render(request, 'queues/partials/settings_form.html', {'queue': queue})
        
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


def dashboard(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    base_url = f"{request.scheme}://{request.get_host()}"
    
    context = {
        'queue': queue,
        
        # URL 1: Kiosk (Untuk iPad/Tablet di Kaunter)
        'kiosk_url': f"{base_url}/q/{slug}/join/", 
        
        # URL 2: Visitor Dashboard (BARU - Untuk QR Code Pelawat)
        # Gunakan 'visitor_join' view yang kita buat tadi
        'visitor_dashboard_url': f"{base_url}/q/{slug}/visitor-join/", 
        
        # URL Lain
        'poster_url': f"{base_url}/q/{slug}/poster/",
        'admin_url': f"{base_url}/q/{slug}/admin/",
        'display_url': f"{base_url}/q/{slug}/display/",
    }
    return render(request, 'queues/dashboard.html', context)

# 3. Page untuk Print QR Poster (Screenshot 3)
def poster_view(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    #join_url = f"http://{request.get_host()}/q/{slug}/join/"
    join_url = f"{request.scheme}://{request.get_host()}/q/{slug}/visitor-join/"
    
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
    
    # Logic: Jika dah penuh atau tutup
    if not queue.allow_join:
        return render(request, 'queues/disabled.html')
    
    # Logic POST (Join Queue)
    if request.method == "POST":
        last_visitor = Visitor.objects.filter(queue=queue).aggregate(Max('number'))
        next_number = (last_visitor['number__max'] or 0) + 1
        
        # Ambil nama (wajib jika setting ON)
        visitor_name = request.POST.get('name')
        if not visitor_name and queue.ask_input:
            messages.error(request, "Sila masukkan nama anda.")
            return redirect('visitor_join', slug=slug)
        
        if not visitor_name: 
            visitor_name = f"Visitor #{next_number}"
        
        new_visitor = Visitor.objects.create(
            queue=queue, 
            name=visitor_name, 
            number=next_number,
            status='WAITING'
        )

        # Notify Admin via WebSocket
        send_socket_update(slug, 'new_visitor', {
            'visitor_id': new_visitor.id,
            'number': f"{new_visitor.number:03d}",
            'name': new_visitor.name
        })
        
        # Simpan ID dalam session supaya user tak hilang tiket bila refresh
        request.session[f'visitor_id_{slug}'] = new_visitor.id
        
        return redirect('visitor_status', visitor_id=new_visitor.id)

    # Cek session: Kalau user dah ada tiket, terus bawa ke status page
    existing_id = request.session.get(f'visitor_id_{slug}')
    if existing_id:
        try:
            visitor = Visitor.objects.get(id=existing_id)
            if visitor.status != 'COMPLETED':
                return redirect('visitor_status', visitor_id=existing_id)
        except Visitor.DoesNotExist:
            del request.session[f'visitor_id_{slug}']

    return render(request, 'queues/visitor_join.html', {'queue': queue})

async def visitor_status(request, visitor_id):
    try:
        # 1. Guna 'aget' (Async Get)
        # 2. Guna 'select_related' supaya data 'queue' diambil sekali (elak error lazy loading)
        visitor = await Visitor.objects.select_related('queue').aget(id=visitor_id)
    except Visitor.DoesNotExist:   
        return render(request, 'queues/session_ended.html')
    
    # Kerana kita dah guna select_related, kita boleh akses visitor.queue tanpa db call baru
    queue = visitor.queue
    
    if visitor.status == 'WAITING':
        # 3. Guna 'acount' (Async Count)
        people_ahead = await Visitor.objects.filter(
            queue=queue, 
            status='WAITING', 
            id__lt=visitor.id
        ).acount() # Perhatikan ada 'a' di depan count
        
        position = people_ahead + 1
    else:
        position = 0
    
    context = {
        'visitor': visitor,
        'queue': queue,
        'position': position
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'queues/partials/visitor_status_content.html', context)
        
    return render(request, 'queues/visitor_status.html', context)


def visitor_quit(request, visitor_id):
    # 1. Cari pelawat berdasarkan ID
    visitor = get_object_or_404(Visitor, id=visitor_id)
    queue_slug = visitor.queue.slug
    
    quit_data = {
        'visitor_id': visitor.id,
        'number': f"{visitor.number:03d}",
        'status': 'quitted'
    }
    visitor.delete()
    send_socket_update(queue_slug, 'visitor_quit', quit_data)
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
    
    # Ambil service type dari form (Anda kena tambah dropdown di HTML nanti)
    service_type = request.POST.get('service_type', 'A') 

    # Kira nombor ikut servis
    last_visitor = Visitor.objects.filter(queue=queue, service_type=service_type).aggregate(Max('number'))
    next_number = (last_visitor['number__max'] or 0) + 1
    
    custom_name = request.POST.get('custom_name')
    if custom_name:
        visitor_name = custom_name
    else:
        visitor_name = f"Visitor #{service_type}{next_number:03d}"
    
    new_visitor = Visitor.objects.create(
        queue=queue,
        name=visitor_name,
        number=next_number,
        service_type=service_type,
        status='WAITING'
    )
    
    # Gunakan ticket_number property
    ticket_str = new_visitor.ticket_number 
    
    messages.success(request, f"Added {visitor_name} ({ticket_str})")
    
    send_socket_update(slug, 'new_visitor', {
        'visitor_id': new_visitor.id,
        'ticket': ticket_str,
        'number': ticket_str,
        'name': new_visitor.name
    })
    
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)

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
    
    # 2. HANTAR SIGNAL WEBSOCKET (KEMASKINI)
    # Kita gunakan event name 'visitor_returned' yang spesifik.
    # Penting: Kita hantar visitor_id supaya frontend tahu siapa yang kena return.
    send_socket_update(slug, 'visitor_returned', {
        'visitor_id': visitor.id,
        # Data lain untuk update display TV dll
        'returned_number': f"{visitor.number:03d}",
        'returned_name': visitor.name
    })
    
    # Jika request dari HTMX (Admin button), return 204 No Content
    if request.headers.get('HX-Request'):
        from django.http import HttpResponse
        return HttpResponse(status=204)
        
    return redirect('admin_interface', slug=slug)


def remove_visitors(request, slug):
    # Fungsi: Kosongkan semua visitor dalam queue ini (Reset)
    queue = get_object_or_404(Queue, slug=slug)
    if request.method == "POST":
        Visitor.objects.filter(queue=queue).delete()
        # Beritahu TV display untuk reset ke 000
        send_socket_update(slug, 'queue_reset', {})
        
        if request.headers.get('HX-Request'):
            return HttpResponse(status=204)
        
    return redirect('admin_interface', slug=slug)

def remove_specific_visitor(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    slug = visitor.queue.slug
    
#     # 1. Padam Visitor
    visitor.delete()
    
#     # 2. Hantar Signal WebSocket (Update List & Counter)
#     # Kita guna signal 'queue_reset' atau 'visitor_quit' pun boleh, 
#     # asalkan frontend refresh list.
    send_socket_update(slug, 'visitor_quit', {})

    if request.headers.get('HX-Request'):
        return HttpResponse(status=204) # Tambah ini
    return redirect('admin_interface', slug=slug)
# Tambah ini di hujung remove_specific_visitor dan invite_specific_visitor



def call_next(request, slug):
    queue = get_object_or_404(Queue, slug=slug)
    counter_name = request.session.get('counter_name', 'General Counter')
    current = Visitor.objects.filter(queue=queue, status='SERVING').first()
    if current:
        current.status = 'COMPLETED'
        current.save()
        
    #next_visitor = Visitor.objects.filter(queue=queue, status='WAITING').order_by('id').first()
    with transaction.atomic():
        next_visitor = Visitor.objects.filter(queue=queue, status='WAITING') \
                                      .select_for_update() \
                                      .order_by('is_returned', 'id') \
                                      .first()
        
    if next_visitor:
        next_visitor.status = 'SERVING'
        next_visitor.served_at = timezone.now()
        next_visitor.served_by = counter_name
        next_visitor.is_invited = True
        next_visitor.save()
        
        # UPDATE FORMAT DI SINI
        ticket_str = next_visitor.ticket_number # Guna property models

        send_socket_update(slug, 'invite_next', {
            'visitor_id': next_visitor.id,
            'ticket': ticket_str,      # Hantar A001
            'number': ticket_str,      # Hantar A001
            'name': next_visitor.name,
            'counter': counter_name,
        })
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)
        
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
    waiting_visitors = Visitor.objects.filter(queue=queue, status='WAITING').order_by('is_returned', 'id')
    waiting_count = waiting_visitors.count()
    next_visitors = [f"{v.number:03d}" for v in waiting_visitors[:3]]
    
    return render(request, 'queues/display.html', {
        'queue': queue,
        'current_serving': current_serving,
        # Pass data ini ke template
        'waiting_count': waiting_count,
        'next_visitors': next_visitors
    })
    
#Dapatkan Data Real-time
def get_realtime_data(queue):
    waiting_visitors = Visitor.objects.filter(queue=queue, status='WAITING') \
                                      .order_by('is_returned', 'id')
    waiting_count = waiting_visitors.count()
    
    # UPDATE SINI: Guna v.ticket_number
    next_3_visitors = [v.ticket_number for v in waiting_visitors[:3]]
    
    return {
        'waiting_count': waiting_count,
        'next_visitors': next_3_visitors
    }
    
def invite_specific_visitor(request, visitor_id):
    visitor = get_object_or_404(Visitor, id=visitor_id)
    queue = visitor.queue
    slug = queue.slug
    counter_name = request.session.get('counter_name', 'General Counter')
    # 1. Selesaikan orang semasa (jika ada)
    current = Visitor.objects.filter(queue=queue, status='SERVING').first()
    if current:
        current.status = 'COMPLETED'
        current.save()

    # 2. Set pelawat yang DIPILIH sebagai serving
    visitor.status = 'SERVING'
    if not visitor.served_at:
        visitor.served_at=timezone.now()
    visitor.served_by = counter_name
    visitor.is_invited = True
    visitor.save()
    ticket_str = visitor.ticket_number

    
    
    # 3. Hantar Signal (Logic ini automatik update list next visitors di TV)
    # Hantar Signal ke WebSocket
    send_socket_update(slug, 'invite_next', {
        'ticket': ticket_str,   # A001
        'number': ticket_str,   # A001
        'name': visitor.name,
        'counter': visitor.served_by,
    })

    if request.headers.get('HX-Request'):
        return HttpResponse(status=204)

    return redirect('admin_interface', slug=slug)
