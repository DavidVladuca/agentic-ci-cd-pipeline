import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class EmailAddressContractTest {
    @Test
    void caseInsensitiveEqualEmailsCollapseInHashSet() {
        Set<EmailAddress> emails = new HashSet<>();

        emails.add(new EmailAddress("User@Example.com"));
        emails.add(new EmailAddress("user@example.com"));

        assertEquals(1, emails.size());
        assertTrue(emails.contains(new EmailAddress("USER@example.com")));
    }
}
