from django.db.models import QuerySet
from .models import Place
from .views_fun import get_annotated_places

class PlaceListView:
    def get_queryset(self) -> QuerySet[Place]:
        if not hasattr(self, '_queryset'):
            self._queryset = get_annotated_places()  # Using a function from views_fun.py
        return self._queryset 