# utility_app/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    path('login/', LoginView.as_view(), name='api_login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('users/', UserListCreateView.as_view(), name='user_list_create'),
    path('create-user/', create_user_view, name='create_user'),
    path('user-page/', user_page_view, name='user_page'),
    path('users/<int:id>/', UserDetailView.as_view(), name='user_detail'),
    path('active-tags/', ActiveTagsView.as_view(), name='active_tags'),
    path('active-schedules/', ActiveSchedulesView.as_view(), name='active_schedules'),
    path('top-tags/', TopTagsView.as_view(), name='top_tags'),
    
    path('home/', home_view, name='home'),
    
    path('config/', config_view, name='config'), 
    path('config/add/', add_tag_view, name='add_tag'),
    path('tags/', TagCreateView.as_view(), name='tag_create'),
    path('tags/list/', TagListView.as_view(), name='tag_list'), 
     path('tags/list/<int:tag_id>/', TagListView.as_view(), name='tag_detail'),  # For PATCH/DELETE with tag_id
    
    path('connection/', connection_view, name='connection'),
     
    path('connect/', ConnectView.as_view(), name='connect_api'),
    path('controls/', ControlView.as_view(), name='control_api'),
    path('control/', control_page, name='control_page'),
    
    path('scheduled/', scheduled_view, name='scheduled'),
    
    path('scheduled/add/', add_schedule_view, name='add_schedule'),
    path('schedules/<int:schedule_id>/', ScheduleView.as_view(), name='schedule_detail'),
    
    path('schedules/', ScheduleView.as_view(), name='schedule_list'),
    path('scheduled/update/<int:schedule_id>/', update_schedule_view, name='update_schedule'),
    
    path('report/', report_view, name='report_view'),
    path('tag-history/', TagHistoryReportView.as_view(), name='tag_history_report'),
    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path('tag-history/export/', TagHistoryExportView.as_view(), name='tag-history-export'),
    
    path('', login_page_view, name='login_page'),
    # path('tags/edit/<int:tag_id>/', TagEditView.as_view(), name='tag_edit'),
]