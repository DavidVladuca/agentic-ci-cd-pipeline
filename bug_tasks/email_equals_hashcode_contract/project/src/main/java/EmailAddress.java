public class EmailAddress {
    private final String value;

    public EmailAddress(String value) {
        if (value == null) {
            throw new IllegalArgumentException("value");
        }

        this.value = value;
    }

    public String value() {
        return value;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }

        if (!(other instanceof EmailAddress)) {
            return false;
        }

        EmailAddress that = (EmailAddress) other;
        return this.value.equalsIgnoreCase(that.value);
    }

    @Override
    public int hashCode() {
        return value.hashCode();
    }
}
