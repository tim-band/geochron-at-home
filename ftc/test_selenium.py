from django.core import mail
from django.test import tag, LiveServerTestCase
from django.urls import reverse
from pathlib import Path
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
import glob
import os
import re
import tempfile
import time

def retrying(retries, f, delay=1):
    if retries == 1:
        return f()
    else:
        try:
            return f()
        except:
            time.sleep(delay)
            return retrying(retries - 1, f)

def almost_equal(x, y):
    return abs(x - y) < 1e-6

def maybe_click(elt):
    if elt is None:
        return False
    elt.click()
    return True

class BasePage:
    def __init__(self, driver, url=None):
        self.driver = driver
        self.url = url

    def check(self):
        return self

    def fill_form(self, fields):
        for k,v in fields.items():
            elt = self.driver.find_element(By.CSS_SELECTOR,  '*[name="{0}"]'.format(k))
            if v is None:
                pass
            elif type(v) is bool:
                if v != elt.is_selected():
                    elt.click()
            else:
                if elt.tag_name.lower() == 'select':
                    elt.click()
                    opt = elt.find_element(By.CSS_SELECTOR,  'option[value="{0}"]'.format(v))
                    assert opt
                    opt.click()
                else:
                    elt.clear()
                    vs = v if type(v) is list else [v]
                    for v in vs:
                        elt.send_keys(v)

    def submit(self, until_fn=None):
        url = self.driver.current_url
        self.driver.find_element(By.CSS_SELECTOR,  'input[type="submit"]').click()
        if until_fn is None:
            until_fn = lambda d: d.current_url != url
        WebDriverWait(self.driver, timeout=2).until(until_fn)

    def element_is_disabled(self, elt):
        if type(elt) is str:
            elt = self.driver.find_element(By.ID, elt)
        return 'leaflet-disabled' in elt.get_attribute('class').split(' ')

    def scroll_into_view(self, elt):
        r = elt.rect
        wr = self.driver.get_window_rect()
        js = 'window.scroll({0},{1})'.format(
            r['x'] + (r['width'] - wr['width'])/2,
            r['y'] + (r['height'] - wr['height'])/2
        )
        self.driver.execute_script(js)

    def find_by_id(self, id):
        return WebDriverWait(self.driver, timeout=2).until(
            lambda d: d.find_element(By.ID, id)
        )

    def find_by_css(self, css):
        return WebDriverWait(self.driver, timeout=2).until(
            lambda d: d.find_element(By.CSS_SELECTOR, css)
        )

    def find_by_xpath(self, xpath, timeout=3):
        return WebDriverWait(
            self.driver,
            timeout=timeout
        ).until(
            lambda d: d.find_element(By.XPATH, xpath)
        )

    def wait_until(self, fn, timeout=2):
        """
        Repeatedly calls fn (with argument driver) until either
        timeout seconds is reached (in which case an exception
        is thrown) or fn returns a truthy value.
        """
        return WebDriverWait(
            self.driver,
            timeout=timeout,
            ignored_exceptions=[
                exceptions.StaleElementReferenceException,
                exceptions.ElementNotInteractableException,
                exceptions.WebDriverException,
            ]
        ).until(fn)

    def get(self, url):
        def get_fn(driver):
            driver.get(url)
            return True
        self.wait_until(get_fn)
        return self

    def click_element(self, by, locator):
        self.wait_until(
            lambda d: maybe_click(d.find_element(by, locator))
        )

    def click_by_id(self, id):
        self.click_element(By.ID, id)

    def click_by_css(self, css):
        self.click_element(By.CSS_SELECTOR, css)

    def send_keys_by(self, by, locator, keys):
        def send_keys(driver):
            e = driver.find_element(by, locator)
            if not e:
                return False
            e.send_keys(keys)
            return True
        self.wait_until(send_keys)

    def send_keys_to_id(self, id, keys):
        self.send_keys_by(By.ID, id, keys)

    def send_keys_to_css(self, css, keys):
        self.send_keys_by(By.CSS_SELECTOR, css, keys)


class HomePage(BasePage):
    check_xpath = '//*[contains(@class,jumbotron)]/p/a[contains(.,"Join us now")]'
    def go(self):
        self.get(self.url + "/ftc")
        return self

    def check(self):
        self.find_by_xpath(self.check_xpath)
        return self

    def is_here(self):
        es = self.driver.find_elements(By.XPATH, self.check_xpath)
        return 0 < len(es)

    def join(self):
        self.driver.find_element(By.CSS_SELECTOR,  "a.btn-success").click()
        return JoinPage(self.driver, self.url)

    def become_guest(self):
        # log on as guest. ProfilePage is returned, which will be wrong if
        # the guest has already done the tutorial (then it will be CountingPage)
        self.get(self.url + "/ftc/counting/guest")
        return ProfilePage(self.driver, self.url)


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
        self.send_keys_to_id("id_username", user.identity)
        self.send_keys_to_id("id_email", user.email)
        self.send_keys_to_id("id_password1", user.password)
        self.send_keys_to_id("id_password2", user.password)
        self.click_element(By.CLASS_NAME, "btn-primary")
        return VerifyPage(self.driver, self.url)


class VerifyPage(BasePage):
    def check(self, user):
        assert "Verify" in self.driver.title
        info = self.driver.find_element(By.CSS_SELECTOR,  "div.alert-info")
        assert user.email in info.text
        return self


class ConfirmPage(BasePage):
    def go(self):
        """
        Fetches the last email sent out and visits the link in it.
        This should be the confirmation email and the link should
        take us to the confirmation page.
        """
        mail_body = mail.outbox[-1].body
        m = re.search(r'http://[a-zA-Z0-9_.:\-@+/]+', mail_body)
        assert(m)
        verification_link = m.group(0)
        self.get(verification_link)
        return self

    def check(self, user):
        assert user.identity in self.driver.find_element(By.CSS_SELECTOR,  "p.lead span.lead").text
        assert user.email in self.driver.find_element(By.CSS_SELECTOR,  "p.lead > a").text
        return self

    def confirm(self):
        self.driver.find_element(By.CSS_SELECTOR,  "button.btn-success").click()
        return SignInPage(self.driver, self.url)


class SignInPage(BasePage):
    def go(self):
        self.get(self.url + "/accounts/login")
        return self

    def sign_in(self, user):
        self.driver.find_element(
            By.CSS_SELECTOR,
            'input[name="login"]'
        ).send_keys(user.identity)
        self.driver.find_element(
            By.CSS_SELECTOR,
            'input[name="password"]'
        ).send_keys(user.password)
        self.driver.find_element(By.CLASS_NAME, "btn-primary").click()
        return ProfilePage(self.driver, self.url)


class TutorialPage(BasePage):
    def check_text_contains(self, text):
        tut_text = self.driver.find_element(By.ID, 'description').text
        assert text in tut_text
        return self

    def go_next(self):
        e = self.find_by_id('next')
        self.scroll_into_view(e)
        e.click()
        return self

    def go_previous(self):
        self.click_by_id('previous')
        return self

    def get_finish_link(self):
        es = self.driver.find_elements(By.ID, 'finish')
        if len(es) == 0:
            return None
        return es[0]

    def go_finish(self):
        self.get_finish_link().click()
        return ProfilePage(self.driver, self.url)

    def get_to_end_and_finish(self):
        while not self.finish_available():
            self.go_next()
        return self.go_finish()

    def finish_available(self):
        link = self.get_finish_link()
        return link is not None

    def check_finish_available(self):
        assert self.finish_available()
        return self

    def check_finish_not_available(self):
        assert not self.finish_available()
        return self

    def check_markers_shown(self):
        assert self.find_by_css('img.leaflet-marker-icon')
        return self


class ProfilePage(BasePage):
    def login_name(self):
        return self.driver.find_element(By.CLASS_NAME, 'fa-user').text

    def check(self):
        self.find_by_xpath("//*[contains(@class,jumbotron)]/h2[contains(.,'Welcome')]")
        return self

    def go(self):
        self.get(self.url + "/accounts/profile")
        return self

    def get_counting_link(self):
        return self.find_by_id('start-counting-link')

    def go_start_counting(self):
        self.get_counting_link().click()
        return CountingPage(self.driver, self.url)

    def check_can_count(self):
        link = self.get_counting_link()
        danger = self.driver.find_elements(By.CLASS_NAME, 'text-danger')
        assert link.get_attribute('disabled') != 'true'
        assert link.get_attribute('href')
        assert not any(['must finish the tutorial' in e.text for e in danger])
        return self

    def check_cannot_count(self):
        link = self.get_counting_link()
        danger = self.driver.find_elements(By.CLASS_NAME, 'text-danger')
        assert link.get_attribute('disabled') == 'true'
        assert link.get_attribute('href') == None
        assert any(['must finish the tutorial' in e.text for e in danger])
        return self

    def go_tutorial(self) -> TutorialPage:
        self.click_by_id('tutorial-link')
        return TutorialPage(self.driver, self.url)

    def go_manage(self):
        self.click_by_id('manage-link')
        return ProjectsPage(self.driver, self.url)


class PublicPage(BasePage):
    def track_count(self):
        elt = self.find_by_id('track-count')
        if elt.text.isnumeric:
            return int(elt.text)
        return None


class GrainViewPage(BasePage):
    def leaflet_image_layer(self):
        mp = self.find_by_id("map")
        return mp.find_element(By.CSS_SELECTOR,  'img.leaflet-image-layer')

    def find_marker(self, x, y):
        lil = self.leaflet_image_layer()
        ms = self.all_markers()
        return find_best(ms, lambda m: sum_squares(
            x * lil.rect['width'] + lil.rect['x'] - pin_x(m),
            y * lil.rect['height'] + lil.rect['y'] - centre_y(m)
        ))

    def all_markers(self):
        return self.driver.find_elements(
            By.CSS_SELECTOR,
            'img.leaflet-marker-icon'
        )

    def image_displayed_url(self):
        class ElementsLoaded:
            def __init__(self, locator_type, locator_string, count):
                self.locator_type = locator_type
                self.locator_string = locator_string
                self.count = count
            def __call__(self, driver):
                es = driver.find_elements(self.locator_type, self.locator_string)
                if len(es) < self.count:
                    return False
                return es

        # we used to wait for all four to be loaded, but now it seems only one
        # gets loaded at a time.
        images = WebDriverWait(self.driver, 3).until(
            ElementsLoaded(By.CLASS_NAME, "leaflet-image-layer", 1))

        return images[-1].get_attribute("src")


class AnalysesPage(BasePage):
    def do_check(self):
        h1s = self.driver.find_elements(By.TAG_NAME, "h1")
        for h1 in h1s:
            if "Analyses of grain" in h1.text:
                return
        raise Exception("Not on Analyses page")

    def check(self):
        retrying(3, self.do_check, 0.3)
        return self

    def go_analysis(self, name) -> GrainViewPage:
        self.find_by_id('analysis-link-{0}'.format(name)).click()
        return GrainViewPage(self.driver, self.url)


class CountingPage(GrainViewPage):
    def check(self):
        self.find_by_id('btn-tracknum')
        return self

    def go(self):
        self.get(self.url + "/ftc/counting")
        return self

    def count(self):
        return self.driver.execute_script(
            'return document.getElementById("tracknum").value;')

    def assert_count(self, count):
        c = self.count()
        assert c == count, "Count should be '{0}' but is '{1}'".format(count, c)
        return self

    def check_count(self, count):
        retrying(
            7,
            lambda: self.assert_count(count),
            0.3
        )
        return self

    def try_click_at(self, x, y):
        mp = self.driver.find_element(By.ID, "map")
        lil = mp.find_element(By.CSS_SELECTOR,  'img.leaflet-image-layer')
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(lil,
            (x - 0.5) * lil.rect["width"], (y - 0.5) * lil.size["height"])
        actions.click().pause(1.0).perform()
        return self

    def click_at(self, x, y):
        retrying(
            3,
            lambda: self.try_click_at(x, y),
            0.3
        )
        return self

    def delete_from(self, minx, maxx, miny, maxy):
        self.click_by_id('ftc-btn-select')
        lil = self.leaflet_image_layer()
        w = lil.size["width"]
        h = lil.size["height"]
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(lil, (minx - 0.5) * w, (miny - 0.5) * h)
        actions.click().pause(1.05)
        actions.move_to_element_with_offset(lil, (maxx - 0.5) * w, (maxy - 0.5) * h)
        actions.click().pause(0.1).perform()
        self.driver.find_element(By.ID, "ftc-btn-delete").click()
        return self

    def drag(self, marker, dx, dy):
        actions = ActionChains(self.driver)
        actions.drag_and_drop_by_offset(marker, dx, dy).perform()
        return self

    def undo(self):
        self.click_by_id("ftc-btn-undo");
        return self

    def redo(self):
        self.click_by_id("ftc-btn-redo");
        return self

    def undo_available(self):
        return not self.element_is_disabled("ftc-btn-undo")

    def redo_available(self):
        return not self.element_is_disabled("ftc-btn-redo")

    def submit(self):
        self.click_by_id("btn-tracknum")
        self.click_by_id("tracknum-submit")
        Alert(self.driver).accept()
        return self

    def save(self):
        self.click_by_id("btn-tracknum")
        self.click_by_id("tracknum-save")
        Alert(self.driver).accept()
        return self

    def previous(self, confirm=False):
        self.click_by_id("btn-tracknum")
        self.click_by_id("tracknum-previous")
        if confirm:
            Alert(self.driver).accept()
        return self

    def next(self, confirm=False):
        self.click_by_id("btn-tracknum")
        self.click_by_id("tracknum-next")
        if confirm:
            Alert(self.driver).accept()
        return self

    def cancel(self, confirm=False):
        self.click_by_id("btn-tracknum")
        self.click_by_id("tracknum-cancel")
        if confirm:
            Alert(self.driver).accept()
        return SamplePage(self.driver, self.url)

    def drag_layer_handle(self, offset):
        track = self.driver.find_element(By.ID, "focus-slider")
        dy = offset * track.size['height']
        handle = self.driver.find_element(By.CLASS_NAME, "noUi-touch-area")
        actions = ActionChains(self.driver)
        actions.drag_and_drop_by_offset(handle, 0, dy).pause(1.0).perform()
        return self


class NavBar(BasePage):
    def get_dropdown(self):
        return self.find_by_css('#account-dropdown a')

    def click_dropdown(self):
        return self.click_by_css('#account-dropdown a')

    def check(self):
        self.get_dropdown()
        return self

    def logout(self):
        home = HomePage(self.driver, self.url)
        class LogsOut:
            def __init__(self, nav_bar):
                self.nav = nav_bar
            def __call__(self, driver):
                if home.is_here():
                    return True
                self.nav.click_dropdown()
                logout = driver.find_element(By.CSS_SELECTOR,
                    'a[href="/accounts/logout/"]'
                )
                if logout.is_displayed() and logout:
                    logout.click()
                    home.check()
                    return True
        self.wait_until(LogsOut(self), timeout=3)
        return home

    def go_manage_projects(self):
        self.click_dropdown()
        self.click_by_css('a[href="/ftc/report/"]')
        return ReportPage(self.driver, self.url)

    def go_edit_projects(self):
        self.click_dropdown()
        self.click_by_id('projects-link')
        return ProjectsPage(self.driver, self.url)


class ReportPage(BasePage):
    def toggle_tree_node(self, name):
        self.driver.find_element(By.XPATH,
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-expander']"
        ).click()
        return self

    def select_tree_node(self, name):
        self.click_element(By.XPATH,
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-checkbox']"
        )
        return self

    def result_now(self, grain_number):
        rows = self.driver.find_elements(By.CSS_SELECTOR, "#results-table tbody tr")
        for r in rows:
            tds = r.find_elements(By.CSS_SELECTOR, "td")
            if 5 <= len(tds) and tds[2].text == grain_number:
                return tds[4].text
        return None

    def result_or_fail(self, grain_number):
        r = self.result_now(grain_number)
        assert r != None, "Grain number {0} not in table".format(grain_number)
        return r

    def result(self, grain_number):
        return retrying(4, lambda: self.result_or_fail(grain_number), 0.1)


class ProjectCreatePage(BasePage):
    def create(self, name, description, priority, closed):
        self.fill_form({
            'project_name': name,
            'project_description': description,
            'priority': priority,
            'closed': closed
        })
        self.submit()
        return ProjectPage(self.driver, self.url)


class ProjectPage(BasePage):
    def create_sample(self):
        self.click_by_id('create-sample')
        return SampleCreatePage(self.driver, self.url)

    def go_sample(self, name):
        self.click_element(
            By.XPATH,
            '//tbody[@id="sample-list"]/tr/td/a[text()="{0}"]'.format(name)
        )
        return SamplePage(self.driver, self.url)


class ProjectsPage(BasePage):
    def go(self):
        self.get(self.url + '/ftc/projects/')
        return self

    def check(self):
        self.find_by_xpath('//h1[text()="Projects"]')
        return self

    def create_project(self):
        self.click_by_id('create-project')
        return ProjectCreatePage(self.driver, self.url)

    def go_project(self, name):
        self.click_element(
            By.XPATH,
            '//tbody[@id="project-list"]/tr/td/a[text()="{0}"]'.format(name)
        )
        return ProjectPage(self.driver, self.url)


class SampleCreatePage(BasePage):
    def create(self, name, property_, priority, min_contributor_num, completed):
        self.fill_form({
            'sample_name': name,
            'sample_property': property_,
            'priority': priority,
            'min_contributor_num': min_contributor_num,
            'completed': completed
        })
        self.submit()
        return SamplePage(self.driver, self.url)


class SamplePage(BasePage):
    def check(self, grain_present=None):
        h1text = self.find_by_css("h1").text
        assert "Sample " in h1text and " of project " in h1text
        if grain_present is not None:
            assert self.grain_present(grain_present)
        return self

    def go(self, pk):
        self.get(self.url + "/ftc/sample/{0}/".format(pk))
        return self

    def create_grain(self):
        self.click_by_id('create-grain')
        return GrainCreatePage(self.driver, self.url)

    def go_grain(self, index):
        self.click_element(
            By.XPATH,
            '//table[@id="grain-set"]/tbody/tr/td/a[text()="{0}"]'.format(index)
        )
        return GrainDetailPage(self.driver, self.url)

    def go_count(self, index):
        self.click_element(
            By.XPATH,
            '//table[@id="grain-set"]/tbody/tr/td/a[@id="count-link-{0}"]'.format(index)
        )
        return CountingPage(self.driver, self.url)

    def go_mica_count(self, index):
        self.click_element(
            By.XPATH,
            '//table[@id="grain-set"]/tbody/tr/td/a[@id="count-mica-link-{0}"]'.format(index)
        )
        return CountingPage(self.driver, self.url)

    def go_public(self, index):
        self.click_element(
            By.XPATH,
            '//table[@id="grain-set"]/tbody/tr/td/a[@id="public-{0}"]'.format(index)
        )
        return PublicPage(self.driver, self.url)

    def go_analyses(self, index):
        self.click_element(
            By.XPATH,
            '//table[@id="grain-set"]/tbody/tr/td/a[@id="analyses-link-{0}"]'.format(index)
        )
        return AnalysesPage(self.driver, self.url)

    def grain_present(self, pk):
        es = self.driver.find_elements(
            By.XPATH,
            '//table[@id="grain-set"]/tbody/tr/td/a[text()="{0}"]'.format(pk)
        )
        return 0 < len(es)

    def edit(self):
        self.click_by_id('edit-sample')
        return SampleEditPage(self.driver, self.url)

    def pk(self):
        bits = self.driver.current_url.split('/')
        n = len(bits)
        last = bits[n - 1] or bits[n - 2]
        return int(last)


class SampleEditPage(BasePage):
    def cancel(self):
        self.click_by_id('cancel')
        return SamplePage(self.driver, self.url)

    def update(self, name, property_, priority, contributor, completed):
        self.fill_form({
            'sample_name': name,
            'sample_property': property_,
            'min_contributor_num': contributor,
            'completed': completed
        })
        self.submit()
        return SamplePage(self.driver, self.url)


class GrainDetailPage(BasePage):
    def check(self):
        self.driver.find_element(By.CSS_SELECTOR, 'table#image-list')
        self.driver.find_element(By.ID, 'id_uploads')
        return self

    def go_zstack(self):
        self.click_by_id('zstack')
        return GrainPage(self.driver, self.url)

    def go_image(self, ft_type, index):
        self.click_element(
            By.XPATH,
            '//table[@id="image-list"]/tbody/tr[td[text()="{0}"]][td[text()="{1}"]]/td/a'.format(ft_type, index)
        )
        return ImagePage(self.driver, self.url)

    def get_grain_index(self):
        title = self.driver.find_element(By.ID, "title").text
        m = re.search(r'Grain (\d+) ', title)
        if m is None:
            return None
        return int(m.group(1))

    def get_image_rows(self):
        headers = [
            th.text
            for th in self.driver.find_elements(
                By.CSS_SELECTOR,
                '#image-list thead th'
            )
        ]
        rows = [[
                td.text
                for td in tr.find_elements(By.CSS_SELECTOR, 'td')
            ] for tr in self.driver.find_elements(
                By.CSS_SELECTOR,
                '#image-list tbody tr'
            )
        ]
        images = []
        for row in rows:
            image = {}
            for i in range(len(headers)):
                image[headers[i]] = row[i]
            images.append(image)
        return images

    def get_pair_element_text(self, id, sep=','):
        t = self.driver.find_element(By.ID, id).text
        return t.split(sep)

    def get_size_element_text(self, id):
        return self.get_pair_element_text(id, sep='\xd7')

    def get_image_size(self):
        return self.get_size_element_text('image-size')

    def get_pixel_size(self):
        return self.get_size_element_text('pixel-size')

    def get_stage_position(self):
        return self.get_size_element_text('stage-position')

    def get_mica_shift(self):
        return self.get_pair_element_text('mica-shift')

    def update(self, paths, fn_detect_update):
        """
        Update with the files given in `paths`, the submission
        will be verified by waiting for `fn_detect_update` (called
        with the driver) to return True.
        """
        self.fill_form({
            'uploads': paths
        })
        self.submit(fn_detect_update)
        return self

    def delete(self):
        self.click_by_id('delete_link')
        return GrainDeletePage(self.driver, self.url)


class GrainDeletePage(BasePage):
    def confirm_delete(self):
        self.click_by_css('input.btn-danger')
        return SamplePage(self.driver, self.url)

    def cancel(self):
        self.click_by_css('a.btn-primary')
        # don't know whether the referrer was
        # the sample page or the grain page
        return None


class GrainCreatePage(BasePage):
    def create(self, paths, index=None):
        self.fill_form({
            'grain_index': index,
            'uploads': paths
        })
        self.submit()
        return GrainDetailPage(self.driver, self.url)


def find_best(a, f):
    """
    Returns the element of `a` for which `f` returns the lowest value
    """
    dist = None
    best = None
    for v in a:
        d = f(v)
        if dist is None or d < dist:
            dist = d
            best = v
    return best


def sum_squares(*a):
    """
    Returns the sum of the squares of the elements of `a`
    """
    total = 0
    for x in a:
        total += x * x
    return total


def pin_x(elt):
    return elt.rect['x'] + elt.rect['width'] / 2

def pin_y(elt):
    return elt.rect['y'] + elt.rect['height']

def centre_y(elt):
    return elt.rect['y'] + elt.rect['height'] / 2


class GrainPage(BasePage):
    def get_image_width(self):
        return WebDriverWait(
            self.driver,
            timeout=2,
            ignored_exceptions=exceptions.StaleElementReferenceException
        ).until(
            lambda d: d.find_element(
                By.CSS_SELECTOR,
                'img.leaflet-image-layer'
            ).rect['width']
        )

    def go_mica(self):
        self.click_by_id('go_mica')
        return self

    def go_grain(self):
        self.click_by_id('go_grain')
        return self

    #def go_update_metadata(self):
    #    self.click_by_id('meta')
    #    return GrainUpdateMetadataPage(self.driver, self.url)

    def go_grain_images(self):
        self.click_by_id('images')
        return GrainDetailPage(self.driver, self.url)

    def zoom_out(self, max_width=600):
        zoom_outs = self.driver.find_elements(
            By.CLASS_NAME, 'leaflet-control-zoom-out'
        )
        assert len(zoom_outs) == 1
        zoom_out = zoom_outs[0]
        while (max_width < self.get_image_width()
                and not self.element_is_disabled(zoom_out)):
            zoom_out.click()

    def edit(self):
        self.zoom_out()
        self.click_by_id('edit')
        return self

    def edit_shift(self):
        self.zoom_out()
        self.click_by_id('edit_shift')
        return self

    def cancel(self):
        self.click_by_id('cancel_edit')
        return self

    def save(self):
        self.click_by_id('save')
        return self

    def check_saved(self):
        self.find_by_css('#edit:not([disabled])')
        self.find_by_css('#save[disabled]')
        self.find_by_css('#cancel_edit[disabled]')
        return self

    def save_shift(self):
        self.click_by_id('save_shift')
        return self

    def check_shift_saved(self):
        self.find_by_css('#edit_shift:not([disabled])')
        self.find_by_css('#save_shift[disabled]')
        self.find_by_css('#cancel_edit[disabled]')
        return self

    def do_partial_drag(self, dragee, dest_x, dest_y):
        drag_x_by = dest_x - pin_x(dragee)
        drag_y_by = dest_y - pin_y(dragee)
        if -2 < drag_x_by and drag_x_by < 2 and -2 < drag_y_by and drag_y_by < 2:
            return False
        max_distance = 99
        drag_x_by = min(max(drag_x_by, -max_distance), max_distance)
        drag_y_by = min(max(drag_y_by, -max_distance), max_distance)
        ActionChains(self.driver).move_by_offset(drag_x_by, drag_y_by).perform()
        return True

    def do_drag(self, dragee, dest_x, dest_y):
        def begin_drag(driver):
            ActionChains(self.driver).click_and_hold(
                dragee
            ).move_by_offset(2, 2).move_by_offset(-2, -2).perform()
            # It seems selenium can grab the image below the marker
            # which makes it look like the marker is moving, but actually
            # the whole image is moving bringing the marker with it.
            # However, if we really have the marker, it will gain this
            # leaflet-drag-target class.
            if 'leaflet-drag-target' in dragee.get_attribute('class'):
                # Success! We have the marker!
                return True
            # Failure! Let's drop whatever we did pick up.
            ActionChains(self.driver).release().perform()
            return False
        WebDriverWait(
            self.driver,
            timeout=2
        ).until(
            begin_drag
        )
        while self.do_partial_drag(dragee, dest_x, dest_y):
            pass
        ActionChains(self.driver).release().perform()

    def marker_elements(self):
        return self.driver.find_elements(
            By.CSS_SELECTOR,
            'img.region-vertex-marker'
        )

    def drag_marker(self, from_x_approx, from_y_approx, to_x, to_y):
        img = self.driver.find_element(By.CSS_SELECTOR, 'img.leaflet-image-layer')
        rect = img.rect
        markers = self.marker_elements()
        marker = find_best(markers, lambda m: sum_squares(
            from_x_approx * rect['width'] + rect['x'] - pin_x(m),
            from_y_approx * rect['height'] + rect['y'] - pin_y(m)
        ))
        self.do_drag(
            marker,
            to_x * rect['width'] + rect['x'],
            to_y * rect['height'] + rect['y']
        )
        return self


class ImagePage(BasePage):
    def delete_image(self):
        self.submit()
        return GrainDetailPage(self.driver, self.url)

    def back(self):
        self.click_by_id('back')
        return GrainDetailPage(self.driver, self.url)


class WebUploader:
    def __init__(self, driver, url):
        self.driver = driver
        self.url = url
        self.script="""
        var url=arguments[0];
        var done=arguments[1];
        var x=new XMLHttpRequest();
        x.open("GET", url);
        x.responseType="arraybuffer";
        x.onload=function() {
            var r=new Uint8Array(x.response);
            var b='';
            var n=r.byteLength;
            for(var i=0;i<n;++i){
                b+=String.fromCharCode(r[i]);
            }
            done(b);
        };
        x.send();
        """

    def upload_projects(self, directory):
        crystal_path = os.path.abspath(directory + '/*/*/*/*/*.jpg')
        files = glob.glob(crystal_path)
        self.hashes = {}
        for f in files:
            number = int( f[ f.rindex('-') + 1 : f.rindex('.') ] )
            with open(f, 'rb') as h:
                contents = h.read()
                hash_ = hash(contents)
                self.hashes[hash_] = number
        navbar = NavBar(self.driver, self.url)
        edit_projects = navbar.go_edit_projects()
        project_page = edit_projects.create_project().create('p1', 'description', 1, False)
        sample_page = project_page.create_sample().create('s1', 'T', 1, 1, False)
        grain_detail_page = sample_page.create_grain().create(files)
        grain_page = grain_detail_page.go_zstack().edit()
        grain_page.drag_marker(0, 0, 0.01, 0.01)
        grain_page.drag_marker(0, 1, 0.01, 0.99)
        grain_page.drag_marker(1, 0, 0.99, 0.01)
        grain_page.drag_marker(1, 1, 0.01, 0.99) # delete by dragging onto 2nd
        grain_page.save().check_saved()

    def get_index(self, file_url):
        ba = self.driver.execute_async_script(self.script, file_url)
        hash_ = hash(ba)
        return self.hashes.get(hash_)

@tag('selenium')
class SeleniumTests(LiveServerTestCase):
    def setUp(self):
        self.project_user = User("admin", "admin@uni.ac.uk", "admin_password")
        self.test_user = User("tester", "tester@test.com", "MyPaSsW0rd")
        self.tmp = None
        browser = os.environ.get('BROWSER')
        if browser == 'firefox':
            self.tmp = tempfile.mkdtemp(prefix='tmp', dir=Path.home())
            self.service = webdriver.firefox.service.Service(service_args=[
                "--profile-root",
                self.tmp,
            ])
            self.driver = webdriver.Firefox(service=self.service)
        elif browser == 'chrome':
            self.driver = webdriver.Chrome()
        else:
            self.driver = webdriver.chromium.webdriver.ChromiumDriver(
                'gah', 'gah',
                service=webdriver.chromium.service.ChromiumService(
                    'chromium.chromedriver',
                    start_error_message='Failed to start chromedriver for Geochron@Home'
                )
            )

    def sign_in(self, user):
        return SignInPage(self.driver, self.live_server_url).go().sign_in(user)

    def tearDown(self):
        self.driver.close()
        if self.tmp is not None:
            os.rmdir(self.tmp)


class WithTutorials(SeleniumTests):
    fixtures = [
        'essential.json',
        'grain_with_images.json',
        'tutorial_pages.json'
    ]
    def test_tutorial_makes_counting_possible(self):
        # sign in as this new user
        profile = SignInPage(self.driver, self.live_server_url).go().sign_in(self.test_user)
        navbar = NavBar(self.driver, self.live_server_url)

        # attempt to count, get a refusal, so do the tutorial
        profile.check_cannot_count()
        tutorial = profile.go_tutorial()
        tutorial.check_text_contains('etched with acid'
        ).check_markers_shown(
        ).check_finish_not_available().go_next(
        ).check_finish_available().go_finish().check()
        navbar.logout()

        # do the same thing with John (checking that test_user's completion does not interfere)
        profile = SignInPage(self.driver, self.live_server_url).go().sign_in(self.project_user)
        profile.check_cannot_count().go_tutorial(
        ).check_markers_shown(
        ).get_to_end_and_finish().check()
        profile.go().check_can_count()
        navbar.logout()

        # check guest cannot count
        HomePage(self.driver, self.live_server_url).become_guest().check_cannot_count(
        ).go_tutorial(
        ).check_markers_shown(
        ).get_to_end_and_finish().check()
        # but then can
        HomePage(self.driver, self.live_server_url).become_guest()
        CountingPage(self.driver, self.live_server_url).check()
        # but then cannot
        navbar.logout()
        HomePage(self.driver, self.live_server_url).become_guest().check_cannot_count()

        # check we can still get counting after logging back in as test_user
        navbar.logout()
        SignInPage(self.driver, self.live_server_url).go().sign_in(
            self.test_user
        ).go_start_counting().check()



class FromCleanWithTutorialsDone(SeleniumTests):
    fixtures = [
        'essential.json',
        'users.json'
    ]
    def test_onboard(self):
        # Upload Z-Stack images
        HomePage(self.driver, self.live_server_url).go()
        profile = SignInPage(self.driver, self.live_server_url).go().sign_in(self.project_user)
        uploader = WebUploader(self.driver, self.live_server_url)
        uploader.upload_projects('test/crystals')
        navbar = NavBar(self.driver, self.live_server_url)
        navbar.logout()

        # create user
        join_page = HomePage(self.driver, self.live_server_url).go().join()
        join_page.check().fill_in(self.test_user).check(self.test_user)
        ConfirmPage(self.driver, self.live_server_url).go().check(self.test_user).confirm()

        profile = SignInPage(self.driver, self.live_server_url).go().sign_in(self.test_user)
        counting = profile.go_start_counting().check()
        self.assertEqual(uploader.get_index(counting.image_displayed_url()), 1)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(0.33).image_displayed_url()), 2)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(0.67).image_displayed_url()), 4)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(-0.33).image_displayed_url()), 3)

    def grain_file_name(self, index, prefix=''):
        n = 'test/crystals/john/p1/s1/Grain01/{1}stack-{0:02d}.jpg'.format(index, prefix)
        return os.path.abspath(n)

    def grain_metadata_file_name(self, index):
        return self.grain_file_name(index) + '_metadata.xml'

    def mica_file_name(self, index):
        return self.grain_file_name(index, 'mica')

    def rois_file_name(self):
        return os.path.abspath('test/crystals/john/p1/s1/Grain01/rois.json')

    def markers_are_square(self, driver):
        zstack = GrainPage(driver)
        elts = zstack.marker_elements()
        if len(elts) != 4:
            return False
        elt_xs = sorted([pin_x(e) for e in elts])
        elt_ys = sorted([pin_y(e) for e in elts])
        return (almost_equal(elt_xs[0], elt_xs[1])
            and almost_equal(elt_xs[2], elt_xs[3])
            and almost_equal(elt_ys[0], elt_ys[1])
            and almost_equal(elt_ys[2], elt_ys[3]))

    def test_manage(self):
        HomePage(self.driver, self.live_server_url).go()
        project = SignInPage(self.driver, self.live_server_url).go().sign_in(
            self.project_user
        ).go_manage().create_project().create(
            "test_manage",
            "project created by test_manage",
            20,
            False
        )
        sample = project.create_sample().create("Sample-1", "T", 20, 99, False)
        grain = sample.create_grain().create([
            self.grain_file_name(1),
            self.mica_file_name(1),
            self.grain_file_name(3)
        ]).check()
        images = grain.get_image_rows()
        self.assertEqual(len(images), 3)
        self.assertDictContainsSubset(
            {
                'format': 'J',
                'ft_type': 'S',
                'index': '1',
                'light_path': 'None',
                'focus': 'None',
            },
            images[0]
        )
        self.assertDictContainsSubset(
            {
                'format': 'J',
                'ft_type': 'S',
                'index': '3',
            },
            images[1]
        )
        # Go to the zstack and check the rois is a rectangle
        zstack = grain.go_zstack().edit()
        WebDriverWait(self.driver, 2).until(self.markers_are_square)
        zstack.cancel().go_mica().edit_shift()
        elts = zstack.marker_elements()
        self.assertEqual(len(elts), 1, msg="should have one marker for mica shift editing")
        shift1_x = pin_x(elts[0])
        shift1_y = pin_y(elts[0])
        zstack.cancel().go_grain_images()
        # Upload a new load of files
        grain.check().update([
            self.grain_file_name(2),
            self.grain_metadata_file_name(1),
            self.grain_file_name(3)
        ], lambda d: d.find_element(
            By.XPATH,
            '//table[@id="image-list"]/tbody/tr/td[text()="T"]'
        ))
        images = grain.get_image_rows()
        self.assertEqual(len(images), 4)
        self.assertListEqual(
            grain.get_image_size(),
            ['201', '202']
        )
        grain.check().update([
            self.grain_file_name(4),
            self.rois_file_name()
        ], lambda d: d.find_element(
            By.XPATH,
            '//table[@id="image-list"]/tbody/tr/td[text()="4"]'
        ))
        self.assertListEqual(
            grain.get_image_size(),
            ['200', '200']
        )
        images = grain.get_image_rows()
        self.assertEqual(len(images), 5)
        self.assertDictContainsSubset(
            {
                'format': 'J',
                'ft_type': 'S',
                'index': '1',
                'light_path': 'T',
                'focus': '20102.55',
            },
            images[0]
        )
        self.assertDictContainsSubset(
            {
                'format': 'J',
                'ft_type': 'S',
                'index': '2',
            },
            images[1]
        )
        self.assertDictContainsSubset(
            {
                'format': 'J',
                'ft_type': 'S',
                'index': '3',
            },
            images[2]
        )
        self.assertDictContainsSubset(
            {
                'format': 'J',
                'ft_type': 'S',
                'index': '4',
            },
            images[3]
        )
        self.assertListEqual(
            grain.get_pixel_size(),
            ['90.79nm', '90.79nm']
        )
        self.assertListEqual(
            grain.get_stage_position(),
            ['30224.66', '11127.77']
        )
        # Go to the zstack and check the rois is now a triangle
        zstack = grain.go_zstack().edit()
        elts = zstack.marker_elements()
        self.assertEqual(len(elts), 3, msg="not three markers")
        elt_xs = sorted([pin_x(e) for e in elts])
        elt_ys = sorted([pin_y(e) for e in elts])
        self.assertAlmostEqual(elt_xs[0], elt_xs[1], msg="left side not straight")
        self.assertNotAlmostEqual(elt_xs[2], elt_xs[1], msg="triangle is flat")
        self.assertNotAlmostEqual(elt_ys[1], elt_ys[2], msg="triangle is flat")
        self.assertAlmostEqual(elt_ys[0], elt_ys[1], msg="bottom side not straight")
        # Check the mica ROI shift
        zstack.cancel().go_mica().edit_shift()
        elts = zstack.marker_elements()
        self.assertEqual(len(elts), 1, msg="should have one marker for mica shift editing")
        shift2_x = pin_x(elts[0])
        shift2_y = pin_y(elts[0])
        self.assertNotAlmostEqual(shift1_x, shift2_x)
        self.assertNotAlmostEqual(shift1_y, shift2_y)
        grain_images = zstack.cancel().go_grain_images()
        [x, y] = grain_images.get_mica_shift()
        self.assertAlmostEqual(float(x), 40)
        self.assertAlmostEqual(float(y), 45)
        # Move the mica shift
        grain_images.go_zstack().go_mica().edit_shift()
        zstack.drag_marker(0.5, 0.5, 0.4, 0.6).save_shift().check_shift_saved().go_grain_images()
        [x, y] = grain_images.get_mica_shift()
        self.assertNotAlmostEqual(float(x), 40)
        self.assertNotAlmostEqual(float(y), 45)

    def test_explicit_grain_index(self):
        HomePage(self.driver, self.live_server_url).go()
        project = SignInPage(self.driver, self.live_server_url).go().sign_in(
            self.project_user
        ).go_manage().create_project().create(
            "test_explicit_grain_index",
            "project created by test_explicit_grain_index",
            20,
            False
        )
        sample = project.create_sample().create("SS2", "T", 20, 99, False)
        sample_pk = sample.pk()
        explicit_index = 54
        grain = sample.create_grain().create([
            self.grain_file_name(1),
            self.mica_file_name(1),
            self.grain_file_name(3)
        ], index=explicit_index).check()
        self.assertEqual(grain.get_grain_index(), explicit_index)
        sample_page = SamplePage(self.driver, self.live_server_url).go(sample_pk).check()
        other_explicit_index = 22
        grain2 = sample_page.create_grain().create([
            self.grain_file_name(2),
            self.mica_file_name(1),
            self.grain_file_name(3)
        ], index=other_explicit_index).check()
        sample_page.go(sample_pk).check().go_grain(
            explicit_index
        ).delete().confirm_delete()
        assert sample.grain_present(other_explicit_index)
        assert not sample.grain_present(explicit_index)


class WithOneGrainUploaded(SeleniumTests):
    fixtures = [
        'essential.json',
        'grain_with_images.json',
        'tutorial_result_admin.json',
        'tutorial_result_tester.json'
    ]

    def test_can_count_tracks(self):
        counting = self.sign_in(self.test_user).go_start_counting().check()
        # start counting tracks
        counting.check_count("000")
        self.assertFalse(counting.undo_available())
        self.assertFalse(counting.redo_available())
        counting.click_at(0.6, 0.35)
        counting.check_count("001")
        self.assertTrue(counting.undo_available())
        self.assertFalse(counting.redo_available())
        counting.undo()
        self.assertFalse(counting.undo_available())
        self.assertTrue(counting.redo_available())
        counting.redo()
        counting.click_at(0.45, 0.5)
        counting.check_count("002")
        # this one is outside of the boundary
        counting.click_at(0.55, 0.55)
        counting.check_count("002")
        counting.click_at(0.52, 0.37)
        counting.check_count("003")
        counting.click_at(0.37, 0.52)
        counting.check_count("004")
        # delete one
        counting.delete_from(0.51, 0.59, 0.33, 0.41)
        counting.check_count("003")
        self.assertTrue(counting.undo_available())
        counting.undo()
        counting.check_count("004")
        self.assertTrue(counting.undo_available())
        self.assertTrue(counting.redo_available())
        counting.undo()
        counting.check_count("003")
        counting.redo()
        counting.check_count("004")
        counting.redo()
        counting.check_count("003")
        self.assertTrue(counting.undo_available())
        self.assertFalse(counting.redo_available())
        counting.undo()
        counting.check_count("004")
        counting.click_at(0.54, 0.35)
        counting.check_count("005")
        self.assertFalse(counting.redo_available())
        self.assertTrue(counting.undo_available())
        marker = counting.find_marker(0.54, 0.35)
        mx1 = marker.rect['x']
        my1 = marker.rect['y']
        counting.drag(marker, 20, -20)
        counting.check_count("005")
        mx2 = marker.rect['x']
        my2 = marker.rect['y']
        # Drag outside the ROI to delete
        counting.drag(marker, 60, 90)
        counting.check_count("004")
        counting.undo()
        counting.check_count("005")
        counting.undo()
        counting.check_count("005")
        marker = counting.find_marker(0.54, 0.35)
        assert marker.rect['x'] == mx1
        assert marker.rect['y'] == my1
        counting.redo()
        counting.check_count("005")
        assert marker.rect['x'] == mx2
        assert marker.rect['y'] == my2
        counting.redo()
        counting.check_count("004")

        # save intermediate result and logout
        counting.save()
        navbar = NavBar(self.driver)
        navbar.logout()

        # login, check no results yet
        profile = SignInPage(self.driver, self.live_server_url).go().sign_in(self.project_user)
        report = navbar.go_manage_projects()
        report.toggle_tree_node("p1")
        report.select_tree_node("s1")
        # Should be no grain "1" in the table yet
        # (as it is a partial save, not a submission)
        self.assertRaises(AssertionError, report.result, "1")
        # start counting, logout
        counting.go().check_count("000")
        navbar.check().logout()

        # login as test user, we should still see the saved result
        profile = SignInPage(self.driver, self.live_server_url).go().sign_in(self.test_user)
        counting = profile.go_start_counting().check()
        counting.check_count("004")

        # submit the result
        counting.submit()

        # see this result, as project admin
        navbar.check().logout().check()
        profile = SignInPage(self.driver, self.live_server_url).go()
        profile.check().sign_in(self.project_user)
        report = navbar.go_manage_projects()
        report.toggle_tree_node("p1")
        report.select_tree_node("s1")
        self.assertEqual(report.result("1"), "4")

class WithTwoGrainsUploaded(SeleniumTests):
    fixtures = [
        'essential.json',
        'grain_with_images.json',
        'grain_with_images5.json',
        'tutorial_result_admin.json',
        'tutorial_result_tester.json'
    ]

    def test_count_link(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').check().go_count(1)
        counting.check()

    def test_revisit_own_count(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_count(1).check()
        self.assertFalse(counting.undo_available())
        self.assertFalse(counting.redo_available())
        counting.click_at(0.6, 0.35)
        counting.click_at(0.5, 0.25)
        counting.check_count("002")
        counting.next(confirm=True)
        counting.check_count("000")
        counting.click_at(0.51, 0.44)
        counting.check_count("001")
        counting.previous(confirm=True)
        counting.check_count("002")
        counting.next()
        counting.check_count("001")
        counting.cancel(confirm=False).check(grain_present=1).go_count(1).check()
        counting.click_at(0.51, 0.24)
        counting.cancel(confirm=True).check(grain_present=1)

    def test_can_count_mica(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_mica_count(1)
        counting.click_at(0.6, 0.35)
        counting.click_at(0.5, 0.25)
        counting.check_count("002")
        counting.next(confirm=True)
        counting.check_count("000")
        # Check that the triangular ROI is flipped:
        # The lower left corner is in the ROI
        counting.click_at(0.75, 0.7)
        counting.check_count("001")
        # The lower right corner is not in the ROI
        counting.click_at(0.25,0.7)
        counting.check_count("001")
        counting.previous(confirm=True)
        counting.check_count("002")
        counting.next()
        counting.check_count("001")
        counting.previous()
        counting.check_count("002")

    def test_mica_shift(self):
        login_page = reverse('account_login')
        self.client.get(login_page)
        r = self.client.post(login_page, {
          'login': self.project_user.identity,
          'password': self.project_user.password
        })
        assert r.status_code < 400
        r = self.client.post(reverse('grain_update_shift', kwargs={
            'pk': 1
        }), {
            'x': 0,
            'y': 20
        })
        assert r.status_code < 400
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_mica_count(1).check()
        # This position is not within the shifted ROI
        counting.click_at(0.75, 0.7)
        counting.check_count("000")
        # But this one is
        counting.click_at(0.75, 0.6)
        counting.check_count("001")

    def test_mineral_does_not_interfere_with_mica_counting(self):
        self.sign_in(self.project_user)
        projects = ProjectsPage(self.driver, self.live_server_url)
        samples = projects.go().check().go_project('p1')
        counting = samples.go_sample('s1').go_count(1)
        retrying(3, lambda: counting.click_at(0.6, 0.35))
        counting.click_at(0.5, 0.25)
        counting.check_count("002").submit()
        # we must wait for the new grain to appear
        retrying(3, lambda: counting.check_count("000"))
        projects.go()
        projects.check()
        samples = projects.go_project('p1')
        counting = samples.go_sample('s1').go_mica_count(1)
        counting.check_count("000").next().check_count("000")
        counting.click_at(0.75, 0.7).check_count("001")
        counting.previous(confirm=True)
        retrying(3, lambda: counting.check_count("000"))
        counting.next()
        counting.check_count("001").submit()
        projects.go()
        report = NavBar(self.driver).go_manage_projects()
        report.toggle_tree_node("p1")
        report.select_tree_node("s1")
        self.assertEqual(report.result("1"), "2")
        self.assertEqual(report.result("5"), "1")

class OneGrainWithoutMica(SeleniumTests):
    fixtures = [
        'essential.json',
        'grain_with_images.json',
        'grain_with_images_mineral_only.json',
        'grain_with_images5.json',
        'tutorial_result_admin.json',
        'tutorial_result_tester.json'
    ]

    def test_mica_count_goes_past_grain_with_no_mica_images(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_count(1).check()
        assert self.driver.current_url.endswith('/1/')
        counting.next().check()
        assert self.driver.current_url.endswith('/3/')
        counting.next().check()
        assert self.driver.current_url.endswith('/5/')
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_mica_count(1).check()
        assert self.driver.current_url.endswith('/1/')
        counting.next().check()
        assert self.driver.current_url.endswith('/5/')

class OneGrainWithoutMineral(SeleniumTests):
    fixtures = [
        'essential.json',
        'grain_with_images.json',
        'grain_with_images_mica_only.json',
        'grain_with_images5.json',
        'tutorial_result_admin.json',
        'tutorial_result_tester.json'
    ]

    def test_mineral_count_goes_past_grain_with_no_mineral_images(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_mica_count(1).check()
        assert self.driver.current_url.endswith('/1/')
        counting.next().check()
        assert self.driver.current_url.endswith('/4/')
        counting.next().check()
        assert self.driver.current_url.endswith('/5/')
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_count(1).check()
        assert self.driver.current_url.endswith('/1/')
        counting.next().check()
        assert self.driver.current_url.endswith('/5/')

class GrainsWithDifferentlySizedRegions(SeleniumTests):
    fixtures = [
        'essential.json',
        'grain_with_small_region.json',
        'grain_with_images.json'
    ]

    def within_bounds(self, x, edge, width, margin):
        if margin < 0:
            return edge + margin * width < x and x <= edge
        else:
            return edge <= x and x < edge + margin * width

    def within_both_bounds(self, x_start, x_width, container_start, container_width, margin):
        on_start = self.within_bounds(x_start, container_start, container_width, margin)
        on_end = self.within_bounds(
            x_start + x_width,
            container_start + container_width,
            container_width,
            -margin
        )
        return on_start and on_end

    def assert_all_markers_are_close_to_edge(self, counting):
        map_rect = self.driver.find_element(By.ID, 'map').rect
        p = self.driver.find_element(By.CSS_SELECTOR, '#map svg g path')
        path_rect = p.rect
        margin = 0.2
        assert self.within_both_bounds(
            path_rect['x'], path_rect['width'], map_rect['x'], map_rect['width'], margin
        ) or self.within_both_bounds(
            path_rect['y'], path_rect['height'], map_rect['y'], map_rect['height'], margin
        )

    def test_region_is_zoomed_to_fit(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_count(1).check()
        assert self.driver.current_url.endswith('/1/')
        self.assert_all_markers_are_close_to_edge(counting)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        counting = samples.go_sample('s1').go_count(6).check()
        assert self.driver.current_url.endswith('/6/')
        self.assert_all_markers_are_close_to_edge(counting)

class RegionWithHole(SeleniumTests):
    fixtures = [
        'essential.json',
        'users.json',
        'test_user.json',
        'projects.json',
        'samples.json',
        'grain_with_negative_region.json',
    ]

    def test_cannot_count_tracks_in_hole(self):
        counting = self.sign_in(self.test_user).go_start_counting().check()
        # start counting tracks
        counting.check_count("000")
        counting.click_at(0.1, 0.1)
        counting.check_count("001")
        counting.click_at(0.5, 0.5)
        # this one is inside both boundaries so is in the hole
        counting.check_count("001")
        counting.click_at(0.9, 0.9)
        counting.check_count("002")


class PublicPageResults(SeleniumTests):
    fixtures = [
        'essential.json',
        'grain_with_images.json',
        'grain_with_images_mineral_only.json',
        'results_for_gwi_m.json'
    ]
    def test_public_results_count(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('p1')
        public_page = samples.go_sample('s1').go_public(3).check()
        # There are three tracks, but only two are within the ROI
        assert public_page.track_count() == 2


class AnalysesWithoutRegions(SeleniumTests):
    fixtures = [
        'essential.json',
        'users.json', 'projects.json', 'samples.json',
        'grains.json', 'images.json', 'results_analyst.json'
    ]
    def test_analyses_without_regions_shows_all_markers(self):
        self.sign_in(self.project_user)
        samples = ProjectsPage(self.driver, self.live_server_url).go(
        ).check().go_project('proj1')
        anayses_page = samples.go_sample('adm_samp').go_analyses(1).check()
        grain_view = anayses_page.go_analysis('terry')
        self.assertEqual(len(grain_view.all_markers()), 3)
