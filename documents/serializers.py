from rest_framework import serializers
from .models import Event, EventParticipant, Notification, UserNotification, CustomUser
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

User = get_user_model()

class EventParticipantSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = EventParticipant
        fields = ['user', 'response']

class EventSerializer(serializers.ModelSerializer):
    participants = EventParticipantSerializer(many=True, required=False)

    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'start_time', 'end_time', 'participants', 'event_link']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return {
            'id': str(instance.id),
            'title': instance.title,
            'start': instance.start_time.isoformat(),
            'end': instance.end_time.isoformat(),
            'description': instance.description,
            'participants': [
                participant.user.username for participant in instance.participants.all()
            ],
            'event_link': instance.event_link
        }

    def create(self, validated_data):
        participants_data = validated_data.pop('participants', [])
        event = Event.objects.create(**validated_data)
        for participant_data in participants_data:
            print("User this:", participant_data)
            EventParticipant.objects.create(event=event, **participant_data)
        
        notif = Notification.objects.create(
            title=event.title,
            message=event.description or "You have been invited to a new event.",
            type=Notification.NotificationType.EVENT,
            expires_at=event.end_time,
            is_active=True
        )

        # Step 2: Create UserNotifications for each invited user
        participants = participant_data  # Should be list of user IDs
        
        for participant_data in participants_data:
            print("User this:", participant_data['user'])
            user = participant_data['user']
            UserNotification.objects.create(user=user, notification=notif)
        return event

    def update(self, instance, validated_data):
        participants_data = validated_data.pop('participants', None)
        instance = super().update(instance, validated_data)
        if participants_data is not None:
            # Clear existing participants
            instance.participants.all().delete()
            # Add new participants
            for participant_data in participants_data:
                EventParticipant.objects.create(event=instance, **participant_data)
        return instance