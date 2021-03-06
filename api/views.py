from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.response import Response
from datasets.serializers import ApprovedSerializer, RejectedSerializer
from chatbot.serializers import ChatSubmitSerializer, ChatDetailSerializer, ChatListSerializer, MessageSerializer, ProcessMessageSerializer
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from datasets.models import Approved, Pending, Rejected, Deleted
from chatbot.models import Chat, Message
from rest_framework import generics
from rest_framework import filters
from rest_condition import Or
from .roles import IsSpottedPage, IsHarumi
from rest_framework.reverse import reverse
from rest_framework import status
from django.conf import settings
import requests

from processing.learning import spotted_analysis
# Create your views here.


class ApprovedList(generics.ListAPIView):
    """Lista de Spotteds aprovados pela moderação e pela API."""

    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    queryset = Approved.objects.all()
    serializer_class = ApprovedSerializer
    filter_backends = (filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'list'
    filter_fields = ('id', 'by_api')
    search_fields = ('message', 'suggestion')
    ordering_fields = ('message', 'by_api', 'id', 'created', 'suggestion')


class RejectedList(generics.ListAPIView):
    """Lista de Spotteds rejeitados pela moderação e pela API."""

    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    queryset = Rejected.objects.all()
    serializer_class = RejectedSerializer
    filter_backends = (filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'list'
    filter_fields = ('id', 'by_api')
    search_fields = ('message', 'suggestion', 'reason')
    ordering_fields = ('message', 'by_api', 'id', 'created', 'suggestion', 'reason')


class ProcessNewSpotted(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = [Or(IsAdminUser, IsSpottedPage), ]
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'new_spotted'

    def post(self, request):
        content = {
            'message': request.data['message'],
            'is_safe': request.data['is_safe'],
            'has_attachment': request.data.get('has_attachment', False),
            'user': request.user,
        }

        if isinstance(content['is_safe'], str):
            content['is_safe'] = eval(content['is_safe'])
        if isinstance(content['has_attachment'], str):
            content['has_attachment'] = eval(content['has_attachment'])

        if content['user'].username != 'localhost':
            publish, suggestion, percentage = spotted_analysis(content['message'])
            reason = suggestion
            if publish and percentage > 0.70:
                action = "approve"
            elif not publish and percentage < 0.3:
                action = "reject"
            else:
                action = "moderation"
        else:
            publish, suggestion, percentage = spotted_analysis(content['message'])
            reason = suggestion
            if publish and percentage > 0.70:
                action = "approve"
            elif not publish and percentage < 0.3:
                action = "reject"
            else:
                action = "moderation"

        # Send spotteds that contain attachments to moderation
        if content['has_attachment'] and action == 'approve':
            action = 'moderation'

        if action == "approve":
            n = Approved(message=content['message'], is_safe=content['is_safe'], suggestion=suggestion, origin=content['user'].username, by_api=True)
        elif action == "reject":
            n = Rejected(message=content['message'], is_safe=content['is_safe'], suggestion=suggestion, origin=content['user'].username, by_api=True, reason=reason)
        elif action == "moderation":
            n = Pending(message=content['message'], is_safe=content['is_safe'], suggestion=suggestion, origin=content['user'].username)
        else:
            n = None

        if not content['user'].username == 'localhost':
            n.save()
            nid = n.id

        else:
            nid = -1

        response = {
            'confidence': percentage,
            'action': action,
            'api_id': nid,
            'suggestion': ("Rejeitar - " + suggestion) if not publish else suggestion
        }
        return Response(response)


class ApprovedSpotted(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = [Or(IsAdminUser, IsSpottedPage), ]
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'approved_spotted'

    def post(self, request):
        content = {
            'api_id': request.data['api_id'],
            'user': request.user,
        }

        if not content['user'].username == 'localhost':
            instance = get_object_or_404(Pending, id=content['api_id'])

            n = Approved(message=instance.message, is_safe=instance.is_safe, suggestion=instance.suggestion, origin=content['user'].username)
            n.save()
            nid = n.id
            instance.delete()
        else:
            nid = -1

        response = {
            'api_id': nid,
        }
        return Response(response)


class RejectedSpotted(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = [Or(IsAdminUser, IsSpottedPage), ]
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'rejected_spotted'

    def post(self, request):
        content = {
            'api_id': request.data['api_id'],
            'reason': request.data['reason'],
            'user': request.user,
        }
        if not content['user'].username == 'localhost':
            instance = get_object_or_404(Pending, id=content['api_id'])

            n = Rejected(message=instance.message, is_safe=instance.is_safe, suggestion=instance.suggestion, reason=content['reason'], origin=content['user'].username)
            n.save()
            nid = n.id
            instance.delete()

        else:
            nid = -1

        response = {
            'api_id': nid,
        }
        return Response(response)


class DeletedSpotted(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = [Or(IsAdminUser, IsSpottedPage), ]
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'deleted_spotted'

    def post(self, request):
        content = {
            'api_id': request.data['api_id'],
            'reason': request.data['reason'],
            'by': request.data['by'],
            'user': request.user,
        }

        if not content['user'].username == 'localhost':
            instance = get_object_or_404(Approved, id=content['api_id'])

            n = Deleted(message=instance.message, is_safe=instance.is_safe, suggestion=instance.suggestion, by_api=instance.by_api, reason=content['reason'], by=content['by'], origin=content['user'].username)
            n.save()
            nid = n.id
            instance.delete()

        else:
            nid = -1

        response = {
            'api_id': nid,
        }
        return Response(response)


class RejectOptions(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request):

        response = {
            "opt_1": "Obsceno",
            "opt_2": "Depressivo",
            "opt_3": "Ofensivo",
            "opt_4": "Mais",
            "opt_5": "Assédio",
            "opt_6": "Spam / Propaganda",
            "opt_7": "Off-topic",
            "opt_8": "Repetido"
        }
        return Response(response)


class MyDeleteOptions(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request):

        response = {
            "opt_1": "Digitei errado",
            "opt_2": "Crush errado",
            "opt_3": "Me arrependi",
            "opt_4": "Mais",
            "opt_5": "Prefiro não dizer",
            "opt_8": "Outro"
        }
        return Response(response)


class ForMeDeleteOptions(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request):

        response = {
            "opt_1": "Ofensivo",
            "opt_2": "Obsceno",
            "opt_3": "Inadequado",
            "opt_4": "Mais",
            "opt_5": "Sou Comprometidx",
            "opt_6": "Prefiro não dizer",
            "opt_8": "Outro"
        }
        return Response(response)


# Harumi's View

class HarumiEndpoint(APIView):
    """Se precisar de mais coisa é só avisar."""

    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = [Or(IsAdminUser, IsHarumi), ]

    def get(self, request):

        approved = len(Approved.objects.all())
        rejected = len(Rejected.objects.all())
        deleted = len(Deleted.objects.all())
        pending = len(Pending.objects.all())

        response = {
            'endpoints': {
                'reject_options': reverse('api:reject_options', request=request),
                'my_delete_options': reverse('api:my_delete_options', request=request),
                'forme_delete_options': reverse('api:forme_delete_options', request=request),
            },
            'spotteds': {
                'approved': approved,
                'rejected': rejected,
                'deleted': deleted,
                'pending': pending,
                'total': approved + rejected + deleted + pending
            }
        }

        return Response(response)


class ProcessChatMessage(generics.GenericAPIView):
    serializer_class = ProcessMessageSerializer
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = [Or(IsAdminUser, IsSpottedPage), ]
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'process_chat_message'

    def post(self, request, *args, **kwargs):
        serializer = ProcessMessageSerializer(data=request.data)
        serializer.is_valid(True)
        message = serializer.data['message']

        # Processa mensagem
        # Mágica
        # Fim do processamento
        result = message
        result_status = False

        response = {
            'result': result,
            'result_status': result_status
        }
        return Response(response)


class ChatSubmit(generics.CreateAPIView):
    """Chat Submit.

    Receives data from a new message from the chatbots. If the chat is new, create it.
    Otherwise just append to the conversation.
    """

    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)
    serializer_class = ChatSubmitSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'chatsubmit'

    def create(self, request, *args, **kwargs):
        """Custom Create method.

        Appends origin to the request data
        """
        data = {key: value for key, value in request.data.items()}
        data['origin'] = request.user.username
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_success_headers(self, data):
        return {}


class ChatListView(generics.ListAPIView):
    queryset = Chat.objects.all()
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    serializer_class = ChatListSerializer


class ChatDetailView(generics.RetrieveDestroyAPIView):
    queryset = Chat.objects.all()
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    serializer_class = ChatDetailSerializer


class MessageViewset(viewsets.ReadOnlyModelViewSet):
    queryset = Message.objects.all()
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    serializer_class = MessageSerializer


class CoinhiveStats(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request):

        ch_secret = settings.COINHIVE_SECRET

        site_stats = requests.get("https://api.coinhive.com/stats/site/", params={'secret': ch_secret}).json()
        payout_stats = requests.get("https://api.coinhive.com/stats/payout/", params={'secret': ch_secret}).json()

        if not site_stats['success'] or not payout_stats['success']:
            return Response({'success': False})

        response = {'success': True}
        response['hashesPerSecond'] = site_stats['hashesPerSecond']
        response['hashesTotal'] = site_stats['hashesTotal']
        response['payoutXmr'] = (site_stats['hashesTotal'] / 1000000) * payout_stats['payoutPer1MHashes']
        response['payoutUsd'] = response['payoutXmr'] * payout_stats['xmrToUsd']
        response['source'] = 'https://coinhive.com/info/faq'

        return Response(response)
