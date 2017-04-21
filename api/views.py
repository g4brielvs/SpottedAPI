from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from datasets.serializers import ApprovedSerializer, RejectedSerializer
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from datasets.models import Approved, Pending, Rejected, Deleted
from rest_framework import generics
from rest_framework import filters
from rest_condition import Or
from .roles import IsSpottedPage, IsHarumi
from rest_framework.reverse import reverse

from processing.learning import spotted_analysis
# Create your views here.


class ApprovedList(generics.ListAPIView):
    """
        Lista de Spotteds aprovados pela moderação e pela API.
    """
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    queryset = Approved.objects.all()
    serializer_class = ApprovedSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend, filters.OrderingFilter)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'list'
    filter_fields = ('id', 'by_api')
    search_fields = ('message', 'suggestion')
    ordering_fields = ('message', 'by_api', 'id', 'created', 'suggestion')


class RejectedList(generics.ListAPIView):
    """
        Lista de Spotteds rejeitados pela moderação e pela API.
    """
    authentication_classes = (SessionAuthentication, BasicAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    queryset = Rejected.objects.all()
    serializer_class = RejectedSerializer
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend, filters.OrderingFilter)
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
            'user': request.user,
        }

        if not content['user'].username == 'localhost':
            publish, suggestion = spotted_analysis(content['message'])
            reason = suggestion
            action = "moderation"
        else:
            publish, suggestion = spotted_analysis(content['message'])
            reason = suggestion
            action = "moderation"

        if action == "approve":
            n = Approved(message=content['message'], is_safe=content['is_safe'], suggestion=suggestion, by_api=True)
        elif action == "reject":
            n = Rejected(message=content['message'], is_safe=content['is_safe'], suggestion=suggestion, by_api=True, reason=reason)
        elif action == "moderation":
            n = Pending(message=content['message'], is_safe=content['is_safe'], suggestion=suggestion)
        else:
            n = None

        if not content['user'].username == 'localhost':
            n.save()
            nid = n.id

        else:
            nid = -1

        response = {
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

            n = Approved(message=instance.message, is_safe=instance.is_safe, suggestion=instance.suggestion)
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

            n = Rejected(message=instance.message, is_safe=instance.is_safe, suggestion=instance.suggestion, reason=content['reason'])
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

            n = Deleted(message=instance.message, is_safe=instance.is_safe, suggestion=instance.suggestion, by_api=instance.by_api, reason=content['reason'], by=content['by'])
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
    """Se precisar de mais coisa é só avisar"""
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
