"""from https://github.com/ms7m/notify-py."""

import codecs
import subprocess as sp
import tempfile
import uuid
from xml.etree import ElementTree


class WindowsNotifier:
    PS1 = """\
[Windows.UI.Notifications.ToastNotificationManager,\
 Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification,\
 Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument,\
 Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$APP_ID = '{app_id}'

$template = @'
{template}
'@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
"""

    def __init__(self, app_id='Python Script', icon: str | None = None):
        self._app_id = app_id
        self._icon = icon

    @classmethod
    def _generate_xml(
        cls,
        title: str,
        message: str,
        app_id: str,
        icon: str | None = None,
    ):
        # Create the top <toast> element
        top = ElementTree.Element('toast')
        # set the duration for the top element
        top.set('duration', 'short')

        # create the <visual> element
        visual = ElementTree.SubElement(top, 'visual')

        # create <binding> element
        binding = ElementTree.SubElement(visual, 'binding')
        # add the required attribute for this.
        # For some reason, go-toast set the template attribute to 'ToastGeneric'
        # but it never worked for me.
        binding.set('template', 'ToastImageAndText02')

        # create <image> element
        image = ElementTree.SubElement(binding, 'image')
        # add an Id
        image.set('id', '1')
        # add the src
        image.set('src', icon or '')

        # add the message and title
        title_element = ElementTree.SubElement(binding, 'text')
        title_element.set('id', '1')
        title_element.text = title

        message_element = ElementTree.SubElement(binding, 'text')
        message_element.set('id', '2')
        message_element.text = message

        # Great we have a generated XML notification.
        # We need to create the rest of the .ps1 file
        # and dump it to the temporary directory
        template = ElementTree.tostring(top, encoding='UTF-8').decode('UTF-8')
        return cls.PS1.format(app_id=app_id, template=template)

    def send(
        self,
        title: str,
        message: str | None = None,
        app_id: str | None = None,
        icon: str | None = None,
    ):
        app_id = app_id or self._app_id
        icon = icon or self._icon
        xml = self._generate_xml(
            title=title, message=message or '', app_id=app_id, icon=icon
        )

        # open the temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = f'{uuid.uuid4()}.ps1'

            with codecs.open(f'{temp_dir}/{filename}', 'w', encoding='UTF-8-SIG') as f:
                f.write(xml)

            # execute the file
            args = ['Powershell', '-ExecutionPolicy', 'Bypass', '-File', filename]
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            sp.check_output(args, cwd=temp_dir, startupinfo=startupinfo)
