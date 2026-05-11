package report;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class UserReportTest {
    @Test
    void formatsUserName() {
        UserReport report = new UserReport();

        assertEquals("ALICE", report.userLine(" alice "));
    }
}
