import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CartHiddenTest {
    @Test
    void quantityGreaterThanOneIsMultiplied() {
        Product product = new Product("Book", 1200);
        Cart cart = new Cart();

        cart.add(new LineItem(product, 3));

        assertEquals(3600, cart.totalCents());
    }

    @Test
    void multipleItemsAreSummedWithQuantities() {
        Product book = new Product("Book", 1200);
        Product pen = new Product("Pen", 150);
        Cart cart = new Cart();

        cart.add(new LineItem(book, 2));
        cart.add(new LineItem(pen, 3));

        assertEquals(2850, cart.totalCents());
    }

    @Test
    void emptyCartTotalIsZero() {
        Cart cart = new Cart();

        assertEquals(0, cart.totalCents());
    }
}