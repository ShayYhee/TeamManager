from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Event, EventParticipant, Notification, UserNotification, CustomUser
import logging

logger = logging.getLogger(__name__)

CustomUser = get_user_model()

class EventParticipantSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all()  # Will be filtered by tenant in __init__
    )

    class Meta:
        model = EventParticipant
        fields = ['user', 'response']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter user queryset by tenant if context is available
        if self.context.get('request'):
            tenant = self.context['request'].tenant
            self.fields['user'].queryset = CustomUser.objects.filter(tenant=tenant)

    def validate_user(self, value):
        # Ensure the selected user belongs to the same tenant as the request
        request = self.context.get('request')
        if request and value.tenant != request.tenant:
            logger.error(f"Invalid user {value.username}: tenant mismatch")
            raise serializers.ValidationError("Selected user does not belong to your tenant.")
        return value

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

    def validate(self, data):
        # Ensure the event's tenant matches the request's tenant
        request = self.context.get('request')
        if request and 'tenant' not in data:
            data['tenant'] = request.tenant
        elif request and data.get('tenant') != request.tenant:
            logger.error(f"Invalid tenant for event creation: {data.get('tenant')}")
            raise serializers.ValidationError("Event tenant does not match the request tenant.")
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        participants_data = validated_data.pop('participants', [])
        # Ensure tenant is set for the event
        validated_data['tenant'] = request.tenant
        event = Event.objects.create(**validated_data)

        # Create EventParticipant entries
        for participant_data in participants_data:
            user = participant_data['user']
            participant_data['tenant']= request.tenant
            if user.tenant != request.tenant:
                logger.error(f"Invalid participant {user.username}: tenant mismatch")
                raise serializers.ValidationError(f"User {user.username} does not belong to the tenant.")
            EventParticipant.objects.create(event=event, **participant_data)

        # Create notification for the event
        notif = Notification.objects.create(
            tenant=request.tenant,
            title=event.title,
            message=event.description or "You have been invited to a new event.",
            type=Notification.NotificationType.EVENT,
            expires_at=event.end_time,
            is_active=True
        )

        # Create UserNotifications for each participant
        for participant_data in participants_data:
            user = participant_data['user']
            UserNotification.objects.create(
                tenant=request.tenant,
                user=user,
                notification=notif
            )
        return event

    def update(self, instance, validated_data):
        request = self.context.get('request')
        # Ensure the event being updated belongs to the tenant
        if instance.tenant != request.tenant:
            logger.error(f"Unauthorized update attempt on event {instance.id} by user {request.user.username}")
            raise serializers.ValidationError("You are not authorized to update this event.")
        
        participants_data = validated_data.pop('participants', None)
        instance = super().update(instance, validated_data)
        if participants_data is not None:
            # Clear existing participants
            instance.participants.all().delete()
            # Add new participants
            for participant_data in participants_data:
                user = participant_data['user']
                if user.tenant != request.tenant:
                    logger.error(f"Invalid participant {user.username}: tenant mismatch")
                    raise serializers.ValidationError(f"User {user.username} does not belong to the tenant.")
                EventParticipant.objects.create(event=instance, **participant_data)
        return instance