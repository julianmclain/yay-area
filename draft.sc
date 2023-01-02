import java.io._
import $ivy.`com.lihaoyi::scalatags:0.8.2`
import scalatags.Text.all._

val htmlStr = html(
  head(
    script("some script")
  ),
  body(
    h1("This is my title"),
    div(
      p("This is my first paragraph"),
      p("This is my second paragraph")
    )
  )
).toString()

val file = new File("index.html")
val writer = new FileWriter(file)
writer.write(htmlStr)
writer.close()
