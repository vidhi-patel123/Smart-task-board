from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/tasks/', views.all_tasks, name='all_tasks'),
    path('api/tasks/add/', views.add_task, name='add_task'),
    path('api/tasks/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    path('api/tasks/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    path('api/tasks/<int:task_id>/status/', views.task_status, name='task_status'),
]
