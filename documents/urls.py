from django.urls import path
from .views import create_document, document_list, home, send_approved_email, autocomplete_sales_rep, create_from_editor, folder_list, create_folder, upload_file, update_task_status, create_task, task_list, task_detail

urlpatterns = [
    path("create/", create_document, name="create_document"),
    path("list/", document_list, name="document_list"),
    path("", home, name="home"),
    path('autocomplete/sales-rep/', autocomplete_sales_rep, name='autocomplete_sales_rep'),
    path("create-editor/", create_from_editor, name="create_from_editor"),
    # path("send-email/<int:document_id>/", send_approved_email, name="send_approval_email"),
    path('folders/', folder_list, name='folder_list'),
    path('folders/<int:parent_id>/', folder_list, name='folder_list'),
    path('folders/create/', create_folder, name='create_folder'),
    path('folders/upload/', upload_file, name='upload_file'),
    path('tasks/', task_list, name='task_list'),
    path('tasks/create/', create_task, name='create_task'),
    path('tasks/<int:task_id>/update-status/', update_task_status, name='update_task_status'),
    path('tasks/<int:task_id>/', task_detail, name='task_detail'),  # For the "View" button
]
