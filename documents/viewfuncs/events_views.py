from django.db import models
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from documents.models import Event, CustomUser, EventParticipant
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, status
from documents.serializers import EventSerializer, UserSerializer    
from rest_framework.views import APIView


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Event.objects.filter(
            models.Q(created_by=user) | models.Q(participants__user=user),
            tenant=user.tenant
        ).distinct()

    def perform_create(self, serializer):
        print(f"Receiv ed data: {self.request.data}")
        event = serializer.save(created_by=self.request.user, tenant=self.request.user.tenant)

    def update(self, request, *args, **kwargs):
        event = self.get_object()
        if event.created_by != request.user:
            return Response({"detail": "You can only edit events you created."}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        if event.created_by != request.user:
            return Response({"detail": "You can only delete events you created."}, status=403)
        return super().destroy(request, *args, **kwargs)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Filter users by tenant
        return CustomUser.objects.filter(tenant=self.request.tenant)

class EventParticipantResponseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        tenant = request.tenant
        user = request.user
        print("Event User: ", user)
        response = request.data.get('response')

        if response not in ['accepted', 'declined']:
            return Response({'error': 'Invalid response'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            participant = EventParticipant.objects.get(event_id=event_id, user=user, tenant=tenant)
            participant.response = response
            participant.save()
            return Response({'message': 'Response updated successfully'}, status=status.HTTP_200_OK)
        except EventParticipant.DoesNotExist:
            return Response({'error': 'You are not a participant of this event'}, status=status.HTTP_403_FORBIDDEN)


from django.middleware.csrf import get_token

@login_required
def calendar_view(request):
    # auth_token = None
    CustomUser = get_user_model()
    # if request.user.is_authenticated:
    #     auth_token = Token.objects.get(user=request.user).key if Token.objects.filter(user=request.user).exists() else None
    context = {
        # 'auth_token': auth_token or '',
        'csrf_token': get_token(request),
        'notification_bar_items': [],
        'birthday_others': [],
        'birthday_self': False,
        'users': CustomUser.objects.filter(tenant=request.user.tenant),
    }
    print(f"Context: {context}")  # Debug
    return render(request, 'users/calendar.html', context)