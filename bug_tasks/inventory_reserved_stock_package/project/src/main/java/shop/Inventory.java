package shop;

import java.util.HashMap;
import java.util.Map;

public class Inventory {
    private final Map<String, Integer> stockBySku = new HashMap<>();

    public void addStock(String sku, int quantity) {
        stockBySku.put(sku, stockBySku.getOrDefault(sku, 0) + quantity);
    }

    public int stockOf(String sku) {
        return stockBySku.getOrDefault(sku, 0);
    }

    public boolean reserve(String sku, int quantity) {
        Integer currentStock = stockBySku.get(sku);

        if (currentStock == null) {
            return false;
        }

        if (currentStock > quantity) {
            stockBySku.put(sku, currentStock - quantity);
            return true;
        }

        return false;
    }
}
