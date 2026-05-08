import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class CartPublicTest {
    @Test
    void singleQuantityOneItemReturnsProductPrice() {
        Product product = new Product("Book", 1200);
        Cart cart = new Cart();

        cart.add(new LineItem(product, 1));

        assertEquals(1200, cart.totalCents());
    }

    @Test
    void invalidQuantityThrows() {
        Product product = new Product("Book", 1200);

        assertThrows(IllegalArgumentException.class, () -> new LineItem(product, 0));
    }

    @Test
    void invalidProductPriceThrows() {
        assertThrows(IllegalArgumentException.class, () -> new Product("Broken", -1));
    }
}