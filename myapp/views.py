from django.shortcuts import render
from django.http import HttpResponse, JsonResponse

from rest_framework.decorators import api_view 
from rest_framework.response import Response 
from rest_framework import status

from .utils.clientsIA import ChatGPTClient, GeminiClient

# Create your views here.

def hello_world(request):
    return HttpResponse("Hello, World!")

@api_view(['POST'])
def compare_lab(request):
    data = request.data

    chatgpt_client = ChatGPTClient()
    gemini_client = GeminiClient()

    try:
        response_gpt = chatgpt_client.compareLabs(data)
        response_gemini = gemini_client.compareLabs(data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    response_data = {
        "chatgpt": response_gpt,
        "gemini": response_gemini
    }

    return JsonResponse(response_data, status=status.HTTP_200_OK)

@api_view(['POST'])
def compare_instrucao(request):
    data = request.data

    chatgpt_client = ChatGPTClient()
    gemini_client = GeminiClient()

    try:
        response_gpt = chatgpt_client.compareInstrucao(data)
        response_gemini = gemini_client.compareInstrucao(data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    response_data = {
        "chatgpt": response_gpt,
        "gemini": response_gemini
    }

    return JsonResponse(response_data, status=status.HTTP_200_OK)