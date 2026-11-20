from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("events.urls")),
]
# Fichiers envoyés (photos, MP3). Sur Railway, monter un volume sur MEDIA_ROOT.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
