from pathlib import Path
import json
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUG_TASKS_DIR = PROJECT_ROOT / "bug_tasks"
ROOT_POM = PROJECT_ROOT / "pom.xml"


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def copy_pom(task_root):
    if not ROOT_POM.exists():
        raise RuntimeError(f"Root pom.xml not found: {ROOT_POM}")

    target = task_root / "project" / "pom.xml"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT_POM, target)


def reset_task(task_name):
    task_root = BUG_TASKS_DIR / task_name

    if task_root.exists():
        shutil.rmtree(task_root)

    task_root.mkdir(parents=True, exist_ok=True)
    copy_pom(task_root)

    return task_root


def create_loan_eligibility_two_file():
    task = reset_task("loan_eligibility_two_file")

    write_text(
        task / "task.txt",
        """
Repair LoanApplication, DebtRatioCalculator, and LoanDecisionService.

Rules:
- approve applications only when credit score is at least 700
- reject applications below credit score 700
- approve only when debt ratio is less than or equal to 0.40
- debt ratio is monthlyDebtCents / monthlyIncomeCents using decimal arithmetic
- monthly income must be positive
- preserve all public method names
"""
    )

    write_json(
        task / "task.json",
        {
            "difficulty": "hard",
            "category": "multi-file-boundary-and-arithmetic",
            "description": "Loan approval has both a credit-score boundary bug and an integer-division debt-ratio bug.",
            "expected_error_type": "TEST_FAILURE"
        }
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "LoanApplication.java",
        """
public class LoanApplication {
    private final int creditScore;
    private final int monthlyDebtCents;
    private final int monthlyIncomeCents;

    public LoanApplication(int creditScore, int monthlyDebtCents, int monthlyIncomeCents) {
        this.creditScore = creditScore;
        this.monthlyDebtCents = monthlyDebtCents;
        this.monthlyIncomeCents = monthlyIncomeCents;
    }

    public int creditScore() {
        return creditScore;
    }

    public int monthlyDebtCents() {
        return monthlyDebtCents;
    }

    public int monthlyIncomeCents() {
        return monthlyIncomeCents;
    }

    public boolean hasEligibleCreditScore() {
        return creditScore > 700;
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "DebtRatioCalculator.java",
        """
public class DebtRatioCalculator {
    public double debtRatio(int monthlyDebtCents, int monthlyIncomeCents) {
        if (monthlyIncomeCents <= 0) {
            throw new IllegalArgumentException("monthlyIncomeCents must be positive");
        }

        return monthlyDebtCents / monthlyIncomeCents;
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "LoanDecisionService.java",
        """
public class LoanDecisionService {
    private final DebtRatioCalculator debtRatioCalculator = new DebtRatioCalculator();

    public boolean approve(LoanApplication application) {
        return application.hasEligibleCreditScore()
            && debtRatioCalculator.debtRatio(
                application.monthlyDebtCents(),
                application.monthlyIncomeCents()
            ) <= 0.40;
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "test" / "java" / "LoanDecisionServiceTest.java",
        """
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;

public class LoanDecisionServiceTest {
    @Test
    void rejectsLowCreditScore() {
        LoanDecisionService service = new LoanDecisionService();

        assertFalse(service.approve(new LoanApplication(650, 10_000, 100_000)));
    }
}
"""
    )

    write_text(
        task / "hidden_tests" / "src" / "test" / "java" / "LoanDecisionScenarioTest.java",
        """
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class LoanDecisionScenarioTest {
    @Test
    void creditScoreExactlySevenHundredIsEligible() {
        LoanDecisionService service = new LoanDecisionService();

        assertTrue(service.approve(new LoanApplication(700, 20_000, 100_000)));
    }

    @Test
    void highDebtRatioIsRejectedUsingDecimalArithmetic() {
        LoanDecisionService service = new LoanDecisionService();

        assertFalse(service.approve(new LoanApplication(720, 50_000, 100_000)));
    }

    @Test
    void ratioAtFortyPercentIsAccepted() {
        LoanDecisionService service = new LoanDecisionService();

        assertTrue(service.approve(new LoanApplication(720, 40_000, 100_000)));
    }
}
"""
    )


def create_coupon_import_and_expiry_combo():
    task = reset_task("coupon_import_and_expiry_combo")

    write_text(
        task / "task.txt",
        """
Repair billing.InvoiceService and discounts.CouponRule.

Rules:
- InvoiceService must use discounts.CouponRule.
- CouponRule.isValidOn(date) is valid through and including its expiry date.
- InvoiceService.totalAfterDiscount applies the discount only when the coupon is valid.
- Null coupon means no discount.
- Total must never be negative.
- Preserve package declarations and public method signatures.
"""
    )

    write_json(
        task / "task.json",
        {
            "difficulty": "hard",
            "category": "package-compilation-plus-logic",
            "description": "Project first fails from a wrong package import, then hidden tests expose expiry-date logic.",
            "expected_error_type": "COMPILATION_ERROR"
        }
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "discounts" / "CouponRule.java",
        """
package discounts;

import java.time.LocalDate;

public class CouponRule {
    private final int discountCents;
    private final LocalDate expiresOn;

    public CouponRule(int discountCents, LocalDate expiresOn) {
        this.discountCents = discountCents;
        this.expiresOn = expiresOn;
    }

    public int discountCents() {
        return discountCents;
    }

    public boolean isValidOn(LocalDate date) {
        return date.isBefore(expiresOn);
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "billing" / "InvoiceService.java",
        """
package billing;

import discount.CouponRule;

import java.time.LocalDate;

public class InvoiceService {
    public int totalAfterDiscount(int subtotalCents, CouponRule coupon, LocalDate date) {
        if (coupon == null) {
            return subtotalCents;
        }

        if (!coupon.isValidOn(date)) {
            return subtotalCents;
        }

        return Math.max(0, subtotalCents - coupon.discountCents());
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "test" / "java" / "billing" / "InvoiceServiceTest.java",
        """
package billing;

import discounts.CouponRule;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class InvoiceServiceTest {
    @Test
    void validCouponBeforeExpiryAppliesDiscount() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(200, LocalDate.of(2026, 1, 31));

        assertEquals(
            800,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 1, 1))
        );
    }
}
"""
    )

    write_text(
        task / "hidden_tests" / "src" / "test" / "java" / "billing" / "InvoiceServiceExpiryTest.java",
        """
package billing;

import discounts.CouponRule;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class InvoiceServiceExpiryTest {
    @Test
    void couponIsValidOnExpiryDate() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(200, LocalDate.of(2026, 1, 31));

        assertEquals(
            800,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 1, 31))
        );
    }

    @Test
    void expiredCouponDoesNotApplyDiscount() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(200, LocalDate.of(2026, 1, 31));

        assertEquals(
            1000,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 2, 1))
        );
    }

    @Test
    void discountCannotMakeTotalNegative() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(5000, LocalDate.of(2026, 1, 31));

        assertEquals(
            0,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 1, 1))
        );
    }
}
"""
    )


def create_reservation_overlap_multi_file():
    task = reset_task("reservation_overlap_multi_file")

    write_text(
        task / "task.txt",
        """
Repair TimeRange, Reservation, and ReservationBook.

Rules:
- reservations conflict only when they are for the same room and their time ranges overlap
- reservations in different rooms do not conflict
- adjacent reservations in the same room are allowed
- overlapping reservations in the same room are rejected
- preserve all public constructors and methods
"""
    )

    write_json(
        task / "task.json",
        {
            "difficulty": "hard",
            "category": "multi-file-state-and-time-boundary",
            "description": "Reservation conflict logic ignores room identity and treats adjacent ranges as overlapping.",
            "expected_error_type": "TEST_FAILURE"
        }
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "TimeRange.java",
        """
import java.time.LocalDateTime;

public class TimeRange {
    private final LocalDateTime start;
    private final LocalDateTime end;

    public TimeRange(LocalDateTime start, LocalDateTime end) {
        if (!start.isBefore(end)) {
            throw new IllegalArgumentException("start must be before end");
        }

        this.start = start;
        this.end = end;
    }

    public boolean overlaps(TimeRange other) {
        return !start.isAfter(other.end) && !end.isBefore(other.start);
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "Reservation.java",
        """
public class Reservation {
    private final String roomId;
    private final TimeRange range;

    public Reservation(String roomId, TimeRange range) {
        this.roomId = roomId;
        this.range = range;
    }

    public String roomId() {
        return roomId;
    }

    public TimeRange range() {
        return range;
    }

    public boolean conflictsWith(Reservation other) {
        return range.overlaps(other.range);
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "ReservationBook.java",
        """
import java.util.ArrayList;
import java.util.List;

public class ReservationBook {
    private final List<Reservation> reservations = new ArrayList<>();

    public boolean add(Reservation reservation) {
        for (Reservation existing : reservations) {
            if (existing.conflictsWith(reservation)) {
                return false;
            }
        }

        reservations.add(reservation);
        return true;
    }

    public int size() {
        return reservations.size();
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "test" / "java" / "ReservationBookTest.java",
        """
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class ReservationBookTest {
    @Test
    void acceptsFirstReservation() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation(
            "A",
            new TimeRange(
                LocalDateTime.of(2026, 1, 1, 10, 0),
                LocalDateTime.of(2026, 1, 1, 11, 0)
            )
        )));

        assertEquals(1, book.size());
    }
}
"""
    )

    write_text(
        task / "hidden_tests" / "src" / "test" / "java" / "ReservationConflictTest.java",
        """
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class ReservationConflictTest {
    private TimeRange range(int startHour, int endHour) {
        return new TimeRange(
            LocalDateTime.of(2026, 1, 1, startHour, 0),
            LocalDateTime.of(2026, 1, 1, endHour, 0)
        );
    }

    @Test
    void sameRoomOverlapIsRejected() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation("A", range(10, 12))));
        assertFalse(book.add(new Reservation("A", range(11, 13))));
        assertEquals(1, book.size());
    }

    @Test
    void differentRoomSameTimeIsAllowed() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation("A", range(10, 12))));
        assertTrue(book.add(new Reservation("B", range(10, 12))));
        assertEquals(2, book.size());
    }

    @Test
    void adjacentSameRoomReservationIsAllowed() {
        ReservationBook book = new ReservationBook();

        assertTrue(book.add(new Reservation("A", range(10, 12))));
        assertTrue(book.add(new Reservation("A", range(12, 14))));
        assertEquals(2, book.size());
    }
}
"""
    )


def create_lru_cache_eviction_order():
    task = reset_task("lru_cache_eviction_order")

    write_text(
        task / "task.txt",
        """
Repair LruCache.

Rules:
- get(key) returns the value or null when absent
- get(key) must mark the key as recently used
- put(key, value) inserts or updates the value
- updating an existing key must not evict another key
- when capacity is exceeded, evict the least recently used key
- preserve the generic public API
"""
    )

    write_json(
        task / "task.json",
        {
            "difficulty": "hard",
            "category": "stateful-data-structure",
            "description": "LRU cache does not update recency on get and mishandles updates.",
            "expected_error_type": "TEST_FAILURE"
        }
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "LruCache.java",
        """
import java.util.LinkedHashMap;
import java.util.Map;

public class LruCache<K, V> {
    private final int capacity;
    private final LinkedHashMap<K, V> values = new LinkedHashMap<>();

    public LruCache(int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }

        this.capacity = capacity;
    }

    public V get(K key) {
        return values.get(key);
    }

    public void put(K key, V value) {
        if (values.size() >= capacity) {
            K firstKey = values.keySet().iterator().next();
            values.remove(firstKey);
        }

        values.put(key, value);
    }

    public int size() {
        return values.size();
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "test" / "java" / "LruCacheTest.java",
        """
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class LruCacheTest {
    @Test
    void storesAndRetrievesSingleValue() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);

        assertEquals(1, cache.get("A"));
    }
}
"""
    )

    write_text(
        task / "hidden_tests" / "src" / "test" / "java" / "LruCacheEvictionTest.java",
        """
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

public class LruCacheEvictionTest {
    @Test
    void getRefreshesRecencyBeforeEviction() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);
        cache.put("B", 2);
        assertEquals(1, cache.get("A"));

        cache.put("C", 3);

        assertEquals(1, cache.get("A"));
        assertNull(cache.get("B"));
        assertEquals(3, cache.get("C"));
    }

    @Test
    void updatingExistingKeyDoesNotEvictOtherEntry() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);
        cache.put("B", 2);
        cache.put("A", 10);

        assertEquals(2, cache.size());
        assertEquals(10, cache.get("A"));
        assertEquals(2, cache.get("B"));
    }
}
"""
    )


def create_csv_parser_quoted_fields():
    task = reset_task("csv_parser_quoted_fields")

    write_text(
        task / "task.txt",
        """
Repair CsvParser.parseLine(String line).

Rules:
- comma separates fields only when outside quotes
- quoted fields may contain commas
- escaped quote inside a quoted field is represented by two quote characters
- trailing empty fields must be preserved
- return fields without surrounding quotes
"""
    )

    write_json(
        task / "task.json",
        {
            "difficulty": "hard",
            "category": "parser-state-machine",
            "description": "CsvParser uses simple comma splitting and cannot handle quoted fields or trailing empty fields.",
            "expected_error_type": "TEST_FAILURE"
        }
    )

    write_text(
        task / "project" / "src" / "main" / "java" / "CsvParser.java",
        """
import java.util.Arrays;
import java.util.List;

public class CsvParser {
    public List<String> parseLine(String line) {
        return Arrays.asList(line.split(","));
    }
}
"""
    )

    write_text(
        task / "project" / "src" / "test" / "java" / "CsvParserTest.java",
        """
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CsvParserTest {
    @Test
    void parsesSimpleCsvLine() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("alpha", "bravo", "charlie"),
            parser.parseLine("alpha,bravo,charlie")
        );
    }
}
"""
    )

    write_text(
        task / "hidden_tests" / "src" / "test" / "java" / "CsvParserQuotedFieldsTest.java",
        """
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CsvParserQuotedFieldsTest {
    @Test
    void quotedFieldMayContainComma() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("alpha", "bravo,charlie", "delta"),
            parser.parseLine("alpha,\\"bravo,charlie\\",delta")
        );
    }

    @Test
    void escapedQuotesInsideQuotedFieldAreUnescaped() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("a \\"quoted\\" value", "x"),
            parser.parseLine("\\"a \\"\\"quoted\\"\\" value\\",x")
        );
    }

    @Test
    void trailingEmptyFieldIsPreserved() {
        CsvParser parser = new CsvParser();

        assertEquals(
            List.of("alpha", "bravo", ""),
            parser.parseLine("alpha,bravo,")
        );
    }
}
"""
    )


def main():
    BUG_TASKS_DIR.mkdir(parents=True, exist_ok=True)

    create_loan_eligibility_two_file()
    create_coupon_import_and_expiry_combo()
    create_reservation_overlap_multi_file()
    create_lru_cache_eviction_order()
    create_csv_parser_quoted_fields()

    print("Created Phase 23 hard benchmark tasks:")
    print("- loan_eligibility_two_file")
    print("- coupon_import_and_expiry_combo")
    print("- reservation_overlap_multi_file")
    print("- lru_cache_eviction_order")
    print("- csv_parser_quoted_fields")


if __name__ == "__main__":
    main()