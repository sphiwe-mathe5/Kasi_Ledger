from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__' 


class RecognizedItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    quantity = serializers.IntegerField(min_value=0)
    category = serializers.CharField(allow_blank=True, required=False)
    # editable fields the user will fill on the page:
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

class CommitItemsSerializer(serializers.Serializer):
    items = RecognizedItemSerializer(many=True)