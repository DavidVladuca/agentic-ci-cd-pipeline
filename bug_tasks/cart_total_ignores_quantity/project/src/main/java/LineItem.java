public class LineItem {
    private final Product product;
    private final int quantity;

    public LineItem(Product product, int quantity) {
        if (product == null) {
            throw new IllegalArgumentException("product must not be null");
        }

        if (quantity <= 0) {
            throw new IllegalArgumentException("quantity must be positive");
        }

        this.product = product;
        this.quantity = quantity;
    }

    public int lineTotalCents() {
        return product.getPriceCents();
    }

    public int getQuantity() {
        return quantity;
    }

    public Product getProduct() {
        return product;
    }
}