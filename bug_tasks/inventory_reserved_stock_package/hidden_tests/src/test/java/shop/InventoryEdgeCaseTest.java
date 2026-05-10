package shop;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class InventoryEdgeCaseTest {
    @Test
    void reserveExactlyAvailableStock() {
        Inventory inventory = new Inventory();
        inventory.addStock("A", 10);

        assertTrue(inventory.reserve("A", 10));
        assertEquals(0, inventory.stockOf("A"));
    }

    @Test
    void reserveUnknownSkuFails() {
        Inventory inventory = new Inventory();

        assertFalse(inventory.reserve("missing", 1));
    }

    @Test
    void reserveZeroOrNegativeQuantityFails() {
        Inventory inventory = new Inventory();
        inventory.addStock("A", 10);

        assertFalse(inventory.reserve("A", 0));
        assertFalse(inventory.reserve("A", -2));
        assertEquals(10, inventory.stockOf("A"));
    }
}
