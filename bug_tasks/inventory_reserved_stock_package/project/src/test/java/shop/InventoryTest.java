package shop;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class InventoryTest {
    @Test
    void reserveLessThanAvailableStock() {
        Inventory inventory = new Inventory();
        inventory.addStock("A", 10);

        assertTrue(inventory.reserve("A", 3));
        assertEquals(7, inventory.stockOf("A"));
    }
}
