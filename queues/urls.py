from django.urls import path
from . import views

urlpatterns = [
    path('', views.create_queue, name='create_queue'), # Screenshot 1 & 4
    # --- PUBLIC / VISITOR PAGES ---
    path('q/<slug:slug>/join/', views.kiosk_join, name='kiosk_join'),  # Kiosk Mode
    path('q/<slug:slug>/dashboard/', views.dashboard, name='dashboard'),
    path('q/<slug:slug>/display/', views.status_display, name='status_display'),
    path('q/<slug:slug>/poster/', views.poster_view, name='poster_view'),
    
    # --- VISITOR SPECIFIC (ID Based) ---
    path('q/visitor/<int:visitor_id>/status/', views.visitor_status, name='visitor_status'),
    path('q/visitor/<int:visitor_id>/quit/', views.visitor_quit, name='visitor_quit'),
    path('q/visitor/<int:visitor_id>/invite/', views.invite_specific_visitor, name='invite_specific_visitor'),
    path('q/visitor/<int:visitor_id>/remove/', views.remove_specific_visitor, name='remove_specific_visitor'),
    path('q/visitor/<int:visitor_id>/return/', views.return_to_queue, name='return_to_queue'),

    # --- ADMIN INTERFACE ---
    path('q/<slug:slug>/admin/', views.admin_interface, name='admin_interface'),
    path('q/<slug:slug>/set-counter/', views.set_counter, name='set_counter'),
    path('q/<slug:slug>/settings/', views.update_queue_settings, name='update_queue_settings'),

    # --- ADMIN ACTIONS (HTMX / Functional) ---
    path('q/<slug:slug>/updates/', views.get_admin_updates, name='get_admin_updates'),
    path('q/<slug:slug>/search/', views.search_visitors, name='search_visitors'),
    path('q/<slug:slug>/call-next/', views.call_next, name='call_next'),
    path('q/<slug:slug>/add-manual/', views.add_manual_visitor, name='add_manual_visitor'),
    path('q/<slug:slug>/remove-all/', views.remove_visitors, name='remove_visitors'),
    path('q/<slug:slug>/visitor-join/', views.visitor_join, name='visitor_join'),
    path('q/<str:slug>/stats/', views.queue_stats, name='queue_stats'),
    path('q/<slug:slug>/remote/', views.admin_remote, name='admin_remote'),
    path('q/visitor/<int:visitor_id>/name/text/', views.visitor_name_text, name='visitor_name_text'),
    path('q/visitor/<int:visitor_id>/name/edit/', views.edit_visitor_name_form, name='edit_visitor_name_form'),
    path('q/visitor/<int:visitor_id>/name/save/', views.save_visitor_name, name='save_visitor_name'),
    path('<slug:slug>/media-content/', views.get_media_content, name='get_media_content'),

]