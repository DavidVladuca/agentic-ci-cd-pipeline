import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class EmailAddressTest {
    @Test
    void sameCaseEmailsAreEqual() {
        assertEquals(
            new EmailAddress("a@example.com"),
            new EmailAddress("a@example.com")
        );
    }
}
