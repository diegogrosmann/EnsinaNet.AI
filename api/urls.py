from django.urls import path,include
from django.views.generic import RedirectView


urlpatterns = [
    #redireciona para a versão 1
    path('compare/', RedirectView.as_view(url='/api/v1/compare/', permanent=True)),

    path('v1/', include(('api.v1.urls', 'api.v1'))),
    #path('v2/', include(('api.v1.urls', 'api.v2'))),
]
