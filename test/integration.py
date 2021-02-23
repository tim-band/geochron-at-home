import unittest
from selenium import webdriver
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import subprocess
import time

def retrying(retries, f):
    if retries == 1:
        f()
    else:
        try:
            f()
        except:
            time.sleep(1)
            retrying(retries - 1, f)


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
        actions.move_to_element_with_offset(mp,
            x * mp.size["width"], y * mp.size["height"])
        actions.click().pause(1.2).perform()
        return self

    def delete_from(self, minx, maxx, miny, maxy):
        self.driver.find_element_by_id("ftc-btn-select").click()
        mp = self.driver.find_element_by_id("map")
        w = mp.size["width"]
        h = mp.size["height"]
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(mp, minx * w, miny * h)
        actions.click().pause(0.1)
        actions.move_to_element_with_offset(mp, maxx * w, maxy * h)
        actions.click().pause(0.1).perform()
        self.driver.find_element_by_id("ftc-btn-delete").click()
        return self

    def submit(self):
        self.driver.find_element_by_id("btn-tracknum").click()
        self.driver.find_element_by_id("tracknum-submit").click()
        Alert(self.driver).accept()
        # Also dismiss "Well done!" message
        retrying(3, lambda: Alert(self.driver).accept())
        return self

    def drag_layer_handle(self, offset):
        track = self.driver.find_element_by_id("slider2")
        dy = offset * track.size['height']
        handle = self.driver.find_element_by_class_name("noUi-touch-area")
        actions = ActionChains(self.driver)
        actions.drag_and_drop_by_offset(handle, 0, dy).pause(1.0).perform()
        return self

    def image_displayed_id(self):
        images = self.driver.find_elements_by_class_name("leaflet-image-layer")
        # find the URI of the last image
        src = images[-1].get_attribute("src")
        # we assume this is the visible one (assuming that
        # all the images are visible and have the same z-index)
        dindex = src.find("stack-") + 6
        return int(src[dindex:dindex+2])


class NavBar(BasePage):
    def logout(self):
        self.driver.find_element_by_css_selector(
            ".navbar-fixed-top .navbar-right a.dropdown-toggle"
        ).click()
        self.driver.find_element_by_css_selector(
            'a[href="/accounts/logout/"]'
        ).click()
        return HomePage(self.driver)

    def go_manage_projects(self):
        self.driver.find_element_by_css_selector(
            ".navbar-fixed-top .navbar-right a.dropdown-toggle"
        ).click()
        self.driver.find_element_by_css_selector(
            'a[href="/ftc/report/"]'
        ).click()
        return ReportPage(self.driver)


class ReportPage(BasePage):
    def toggle_tree_node(self, name):
        self.driver.find_element_by_xpath(
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-expander']"
        ).click()
        return self

    def select_tree_node(self, name):
        self.driver.find_element_by_xpath(
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-checkbox']"
        ).click()
        return self

    def result(self, grain_number):
        return self.driver.find_element_by_css_selector(
            "#mytable tbody td:nth-child(5)"
        ).text


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
        test_user = User("tester", "tester@test.com", "MyPaSsW0rd")
        join_page.check().fill_in(test_user).check(test_user)
        WebMail(self.driver).go().click_first_body_link()
        ConfirmPage(self.driver).check(test_user).confirm()

        # sign in as this new user
        profile = SignInPage(self.driver).go().sign_in(test_user)

        # start counting tracks
        counting = profile.go_start_counting().check()
        self.assertEqual(counting.image_displayed_id(), 1)
        self.assertEqual(counting.drag_layer_handle(0.33).image_displayed_id(), 2)
        self.assertEqual(counting.drag_layer_handle(0.67).image_displayed_id(), 4)
        self.assertEqual(counting.drag_layer_handle(-0.33).image_displayed_id(), 3)
        self.assertEqual(counting.count(), "000")
        counting.click_at(0.6, 0.35)
        self.assertEqual(counting.count(), "001")
        counting.click_at(0.45, 0.5)
        self.assertEqual(counting.count(), "002")
        # this one is outside of the boundary
        counting.click_at(0.55, 0.55)
        self.assertEqual(counting.count(), "002")
        counting.click_at(0.52, 0.37)
        self.assertEqual(counting.count(), "003")
        counting.click_at(0.37, 0.52)
        self.assertEqual(counting.count(), "004")
        # delete one
        counting.delete_from(0.51, 0.59, 0.33, 0.41)
        self.assertEqual(counting.count(), "003")
        # submit the result
        counting.submit()

        # see this result, as project admin
        navbar = NavBar(self.driver)
        navbar.logout()
        project_user = User("john", "john@test.com", "john")
        profile = SignInPage(self.driver).go().sign_in(project_user)
        WebMail(self.driver).go().click_first_body_link()
        ConfirmPage(self.driver).check(project_user).confirm()
        profile = SignInPage(self.driver).go().sign_in(project_user)
        report = navbar.go_manage_projects()
        report.toggle_tree_node("p1")
        report.select_tree_node("s1")
        self.assertEqual(report.result("1"), "3")

    def tearDown(self):
        self.driver.close()
        self.dc.down()


if __name__ == '__main__':
    unittest.main()
