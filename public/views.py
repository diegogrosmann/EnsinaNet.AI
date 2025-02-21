from django.shortcuts import render, redirect

def index(request):
    if request.user.is_authenticated:
        return redirect('accounts:tokens_manage') 
    return render(request, 'public/index.html')
