public class Product {
    private final String name;
    private final int priceCents;

    public Product(String name, int priceCents) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("name must not be blank");
        }

        if (priceCents < 0) {
            throw new IllegalArgumentException("price must not be negative");
        }

        this.name = name;
        this.priceCents = priceCents;
    }

    public String getName() {
        return name;
    }

    public int getPriceCents() {
        return priceCents;
    }
}