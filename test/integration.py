import unittest
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import subprocess

class DockerCompose:
    def __init__(self, yml):
        if yml:
            self.pre = ["docker-compose", "-f", yml]
        else:
            self.pre = ["docker-compose"]

    def down(self):
        subprocess.run(self.pre + ["down"])
        return self

    def up(self):
        subprocess.run(self.pre + ["up", "--force-recreate", "--build", "-d"])
        return self

    def exec(self, *kargs):
        subprocess.run(self.pre + ["exec", "django"] + list(kargs))
        return self

    def init(self):
        self.exec("./site_init.sh")
        return self


class BasePage:
    def __init__(self, driver):
        self.driver = driver


class WebMail(BasePage):
    def go(self):
        self.driver.get("http://localhost:18081/")
        return self

    def click_first_body_link(self):
        self.driver.find_element_by_css_selector("td.body-text p a").click()


class HomePage(BasePage):
    def go(self):
        self.driver.get("http://localhost:18080/ftc")
        return self

    def join(self):
        self.driver.find_element_by_css_selector("a.btn-success").click()
        return JoinPage(self.driver)


class User:
    def __init__(self, identity, email, password):
        self.identity = identity
        self.email = email
        self.password = password


class JoinPage(BasePage):
    def check(self):
        assert "Signup" in self.driver.title
        return self

    def fill_in(self, user):
        self.driver.find_element_by_id("id_username").send_keys(user.identity)
        self.driver.find_element_by_id("id_email").send_keys(user.email)
        self.driver.find_element_by_id("id_password1").send_keys(user.password)
        self.driver.find_element_by_id("id_password2").send_keys(user.password)
        self.driver.find_element_by_class_name("btn-primary").click()
        return VerifyPage(self.driver)


class VerifyPage(BasePage):
    def check(self, user):
        assert "Verify" in self.driver.title
        info = self.driver.find_element_by_css_selector("div.alert-info")
        assert user.email in info.text
        return self


class ConfirmPage(BasePage):
    def check(self, user):
        assert user.identity in self.driver.find_element_by_css_selector("p.lead span.lead").text
        assert user.email in self.driver.find_element_by_css_selector("p.lead > a").text
        return self

    def confirm(self):
        self.driver.find_element_by_css_selector("button.btn-success").click()
        return SignInPage(self.driver)


class SignInPage(BasePage):
    def go(self):
        self.driver.get("http://localhost:18080/accounts/login")
        return self

    def sign_in(self, user):
        self.driver.find_element_by_css_selector('input[name="login"]').send_keys(user.identity)
        self.driver.find_element_by_css_selector('input[name="password"]').send_keys(user.password)
        self.driver.find_element_by_class_name("btn-primary").click()
        return ProfilePage(self.driver)


class ProfilePage(BasePage):
    def login_name(self):
        return self.driver.find_element_by_class_name('fa-user').text

    def go_start_counting(self):
        self.driver.find_element_by_id("start-counting-link").click()
        return CountingPage(self.driver)


class CountingPage(BasePage):
    def check(self):
        self.driver.find_element_by_id("btn-tracknum")
        return self

    def count(self):
        return self.driver.execute_script(
            'return document.getElementById("tracknum").value;')

    def click_at(self, x, y):
        mp = self.driver.find_element_by_id("map")
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(mp, x, y)
        actions.click().pause(1.1).perform()
        return self


class DjangoTests(unittest.TestCase):
    def setUp(self):
        self.dc = DockerCompose("./docker-compose-test.yml").down().up().init()
        self.driver = webdriver.Firefox()

    def test_onboard(self):
        # upload x-rays
        self.dc.exec("python3", "upload_projects.py",
            "-s", "geochron.settings",
            "-i", "test/xrays",
            "-o", "static/grain_pool")

        # create user
        join_page = HomePage(self.driver).go().join()
        self.test_user = User("tester", "tester@test.com", "MyPaSsW0rd")
        join_page.check().fill_in(self.test_user).check(self.test_user)
        WebMail(self.driver).go().click_first_body_link()
        ConfirmPage(self.driver).check(self.test_user).confirm()

        # sign in as this new user
        profile = SignInPage(self.driver).go().sign_in(self.test_user)

        # start counting tracks
        counting = profile.go_start_counting().check()
        self.assertEqual(counting.count(), "000")
        counting.click_at(120, 70)
        self.assertEqual(counting.count(), "001")
        counting.click_at(90, 100)
        self.assertEqual(counting.count(), "002")
        # this one is outside of the boundary
        counting.click_at(110, 110)
        self.assertEqual(counting.count(), "002")
        counting.click_at(105, 75)
        self.assertEqual(counting.count(), "003")

    def tearDown(self):
        self.driver.close()
        self.dc.down()


if __name__ == '__main__':
    unittest.main()
