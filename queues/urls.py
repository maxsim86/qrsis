from django.urls import path
from . import views

urlpatterns = [
    path('', views.create_queue, name='create_queue'), # Screenshot 1 & 4
    path('q/<slug:slug>/dashboard/', views.dashboard, name='dashboard'), # Screenshot 2
    path('q/<slug:slug>/join/', views.visitor_join, name='visitor_join'), # Screenshot 5 (Link QR)
    path('q/<slug:slug>/poster/', views.poster_view, name='poster_view'), # Screenshot 3
    path('q/<slug:slug>/admin/', views.admin_interface, name='admin_interface'), # Screenshot 6
    path('q/<slug:slug>/display/', views.status_display, name='status_display'), # Screenshot 1 (Display)
    
    path('q/<slug:slug>/next/', views.call_next, name='call_next'),
    path('q/<slug:slug>/join/', views.visitor_join, name='visitor_join'), # Page Masukkan Nama
    path('visitor/<int:visitor_id>/status/', views.visitor_status, name='visitor_status'), # Page Bulatan Biru
    path('visitor/<int:visitor_id>/quit/', views.visitor_quit, name='visitor_quit'), # Function Quit
    path('visitor/<int:visitor_id>/return/', views.return_to_queue, name='return_to_queue'),
    path('q/<slug:slug>/remove_all/', views.remove_visitors, name='remove_visitors'),
    #path('visitor/<int:visitor_id>/remove/', views.remove_specific_visitor, name='remove_specific_visitor'),
    path('visitor/<int:visitor_id>/ack/', views.acknowledge_return, name='acknowledge_return'),
    path('visitor/<int:visitor_id>/ack-invite/', views.acknowledge_invite, name='acknowledge_invite'),
    path('q/<slug:slug>/add-manual/', views.add_manual_visitor, name='add_manual_visitor'),
    path('visitor/<int:visitor_id>/invite/', views.invite_specific_visitor, name='invite_specific_visitor'),
    path('q/<slug:slug>/update_settings/', views.update_queue_settings, name='update_queue_settings'),
    path('q/<slug:slug>/set-counter/', views.set_counter, name='set_counter'),
    path('q/<slug:slug>/kiosk/', views.kiosk_join, name='kiosk_join'),
    path('visitor/<int:visitor_id>/remove/', views.remove_specific_visitor, name='remove_specific_visitor'),
    path('visitor/<int:visitor_id>/invite/', views.invite_specific_visitor, name='invite_specific_visitor'),
]