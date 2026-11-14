"""Unit tests for visa sponsorship and work authorization classification."""
import unittest
from app.scraping.sponsorship import classify_sponsorship


class TestSponsorshipClassification(unittest.TestCase):
    def test_motorola_citizenship_classification(self):
        """Motorola Solutions requires unrestricted U.S. work authorization/citizenship."""
        jd = (
            "Basic Requirements:\n"
            "- Working towards a Bachelor's or Master's in Computer Engineering or Computer Science\n"
            "- You are a U.S. Citizen, U.S. permanent resident or possess other unrestricted US work authorization\n"
            "EEO Statement:\n"
            "Motorola Solutions is an Equal Opportunity Employer."
        )
        res = classify_sponsorship(title="Software Engineering Intern - Summer 2027", description=jd)
        self.assertEqual(res["status"], "citizenship")
        self.assertEqual(res["label"], "US Citizen Required")
        self.assertTrue(res["requires_citizenship"])
        self.assertFalse(res["is_f1_eligible"])

    def test_defense_clearance_and_itar(self):
        """Defense, clearance, or ITAR postings require citizenship."""
        postings = [
            ("Systems Engineer Intern", "Must possess or be able to obtain an active Secret security clearance. U.S. citizenship required."),
            ("Aerospace Flight Software Intern", "Role is subject to ITAR export control regulations. Candidates must be a U.S. Person."),
            ("Cybersecurity Defense Analyst", "Requires active DoD Top Secret clearance."),
        ]
        for title, desc in postings:
            with self.subTest(title=title):
                res = classify_sponsorship(title=title, description=desc)
                self.assertEqual(res["status"], "citizenship")
                self.assertEqual(res["label"], "US Citizen Required")

    def test_nbcuniversal_no_sponsorship_classification(self):
        """NBCUniversal explicitly excludes student visa holders and does not sponsor."""
        jd = (
            "Basic Requirements:\n"
            "- Must be presently authorized to work for any employer in the United States and must not require "
            "work visa sponsorship from NBCUniversal now or in the future to retain authorization to work in the United States.\n"
            "For further clarification, candidates currently on any student or exchange visa "
            "(e.g. F-1 CPT, F-1 OPT, J-1, M-1) are not eligible to apply unless they will be able to change or adjust "
            "to another status that grants work authorization without NBCUniversal sponsorship."
        )
        res = classify_sponsorship(title="Software Engineer Intern", description=jd)
        self.assertEqual(res["status"], "no_sponsorship")
        self.assertEqual(res["label"], "No Sponsorship")
        self.assertFalse(res["is_f1_eligible"])

    def test_general_no_sponsorship_phrasings(self):
        """Standard no-sponsorship declarations classify as No Sponsorship."""
        phrasings = [
            "We will not sponsor applicants for work visas now or in the future.",
            "This position does not offer visa sponsorship.",
            "Candidates must be authorized to work in the US without the need for visa sponsorship.",
            "Unable to provide visa sponsorship for this role.",
            "Visa sponsorship is not available.",
        ]
        for text in phrasings:
            with self.subTest(text=text):
                res = classify_sponsorship(title="SWE Intern", description=text)
                self.assertEqual(res["status"], "no_sponsorship")
                self.assertEqual(res["label"], "No Sponsorship")

    def test_explicit_sponsorship_available(self):
        """Postings explicitly offering visa sponsorship or CPT/OPT/H-1B."""
        postings = [
            ("Frontend Engineer Intern", "Visa sponsorship is available for eligible candidates."),
            ("Backend Intern", "We welcome F-1 students! CPT and OPT accepted."),
            ("Machine Learning Intern", "Company offers H-1B visa sponsorship and support."),
            ("Software Engineer Intern", "CPT/OPT eligible applicants are encouraged to apply."),
        ]
        for title, desc in postings:
            with self.subTest(title=title):
                res = classify_sponsorship(title=title, description=desc)
                self.assertEqual(res["status"], "sponsorship_available")
                self.assertEqual(res["label"], "Sponsorship Available")
                self.assertTrue(res["is_f1_eligible"])
                self.assertTrue(res["offers_sponsorship"])

    def test_neutral_posting_untagged(self):
        """Unconfirmed postings without work auth or visa mentions remain untagged."""
        desc = (
            "About the job:\n"
            "We are looking for a Software Engineering Intern to join our team in San Francisco. "
            "You will build high throughput data processing pipelines using Python and PostgreSQL."
        )
        res = classify_sponsorship(title="Software Engineering Intern", description=desc)
        self.assertIsNone(res["status"])
        self.assertIsNone(res["label"])
        self.assertTrue(res["is_f1_eligible"])
        self.assertFalse(res["requires_citizenship"])
        self.assertFalse(res["offers_sponsorship"])

    def test_eeo_boilerplate_does_not_trigger_citizenship(self):
        """EEO boilerplate mentioning citizenship or protected status must not trigger citizenship requirement."""
        desc = (
            "Job Responsibilities:\n"
            "- Develop web applications in TypeScript.\n\n"
            "Equal Employment Opportunity:\n"
            "Our company provides equal employment opportunities to all employees and applicants for employment "
            "without regard to race, color, religion, sex, national origin, age, disability or citizenship status."
        )
        res = classify_sponsorship(title="Software Intern", description=desc)
        # Should not falsely classify as US Citizen Required
        self.assertNotEqual(res["status"], "citizenship")
        self.assertIsNone(res["status"])
        self.assertIsNone(res["label"])


if __name__ == "__main__":
    unittest.main()

