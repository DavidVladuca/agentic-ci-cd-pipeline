package report;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class UserReportHiddenTest {
    @Test
    void formatsDifferentUserName() {
        UserReport report = new UserReport();

        assertEquals("BOB", report.userLine(" bob "));
    }
}
